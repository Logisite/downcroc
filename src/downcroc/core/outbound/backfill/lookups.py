from __future__ import annotations

import time

from downcroc.core.outbound.backfill.evidence import (
    BACKOFF_STEPS,
    TIMEOUT_S,
    ProviderLookup,
    SearchFailure,
)
from downcroc.domain.accounts import Account
from downcroc.domain.attempts import ThreadHole
from downcroc.domain.providers import ProviderSpec
from downcroc.mail.gmail import api as gmail_api
from downcroc.mail.gmail import read
from downcroc.runtime.logging.setup import EventLogger


class Lookups:
    """The Gmail API calls behind one stage-2 lookup turn, with backoff.

    Neither method raises: failures come back as data so the stage can turn
    them into outcomes.
    """

    def __init__(self, log: EventLogger, project_id: str | None = None) -> None:
        self._log = log
        self._project_id = project_id

    def search(
        self, account: Account, spec: ProviderSpec, hole: ThreadHole, token: str
    ) -> read.ThreadSearch | SearchFailure:
        for index, delay in enumerate(BACKOFF_STEPS):
            try:
                return read.find_thread_id(
                    spec,
                    token,
                    hole.message_id,
                    timeout_s=TIMEOUT_S,
                    project_id=self._project_id,
                )
            except gmail_api.GmailApiFailure as error:
                self._log.info(
                    "backfill.backoff",
                    account=account.id,
                    delay_s=delay,
                    cause=error.code,
                    detail=str(error),
                )
                if error.auth:
                    return SearchFailure(error.code, str(error), auth=True)
                if index == len(BACKOFF_STEPS) - 1:
                    return SearchFailure(error.code, str(error), auth=False)
                time.sleep(delay)
        return SearchFailure("gmail_api_unavailable", "search did not complete", False)

    def provider(
        self, account: Account, spec: ProviderSpec, hole: ThreadHole, token: str
    ) -> ProviderLookup:
        message_id = hole.provider_message_id
        if not message_id:
            return ProviderLookup("not_attempted")
        for index, delay in enumerate(BACKOFF_STEPS):
            try:
                message = read.get_message(
                    spec,
                    token,
                    message_id,
                    timeout_s=TIMEOUT_S,
                    fmt="minimal",
                    project_id=self._project_id,
                )
            except gmail_api.GmailApiFailure as error:
                if error.auth:
                    return ProviderLookup("skipped", error=error.code)
                if not error.transient and not error.quota:
                    return ProviderLookup("missing")
                self._log.info(
                    "backfill.backoff",
                    account=account.id,
                    delay_s=delay,
                    cause=error.code,
                    detail=str(error),
                )
                if index == len(BACKOFF_STEPS) - 1:
                    return ProviderLookup("error", error=error.code)
                time.sleep(delay)
                continue
            if message.thread_id:
                return ProviderLookup("hit", thread_id=message.thread_id)
            return ProviderLookup("missing")
        return ProviderLookup("error", error="gmail_api_unavailable")
