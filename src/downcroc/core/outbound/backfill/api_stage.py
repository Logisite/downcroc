from __future__ import annotations

import time
from dataclasses import dataclass

from downcroc.domain.accounts import Account
from downcroc.domain.attempts import ThreadHole
from downcroc.domain.providers import ProviderSpec
from downcroc.mail.gmail import api as gmail_api
from downcroc.mail.gmail import read
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.repositories.send_attempts import SendAttemptRepo

BACKOFF_STEPS = (2.0, 5.0, 15.0, 60.0)
TIMEOUT_S = 30.0


@dataclass(frozen=True)
class Outcome:
    """What one stage-2 turn did to a hole."""

    state: str  # resolved | first | waiting | missing | backoff | skipped


class ApiStage:
    """Stage 2: per-hole Gmail API search with the strike ladder underneath."""

    def __init__(
        self,
        attempts: SendAttemptRepo,
        log: EventLogger,
        *,
        retry_after_days: int,
        project_id: str | None = None,
    ) -> None:
        self._attempts = attempts
        self._log = log
        self._retry_after_days = retry_after_days
        self._project_id = project_id

    def write(
        self,
        account: Account,
        hole: ThreadHole,
        thread_id: str,
        *,
        medium: str,
    ) -> Outcome:
        """Re-read-before-write: a hole filled concurrently is not clobbered."""

        if self._attempts.resolve_thread(hole.attempt_id, thread_id):
            self._log.info(
                "backfill.resolved",
                attempt=hole.attempt_id,
                job=hole.job_id,
                account=account.id,
                medium=medium,
                thread=thread_id,
            )
            return Outcome("resolved")
        return Outcome("skipped")

    def resolve(
        self, account: Account, spec: ProviderSpec, hole: ThreadHole, token: str
    ) -> Outcome:
        """One search turn. Never raises: failures come back as outcomes."""

        for index, delay in enumerate(BACKOFF_STEPS):
            try:
                page = read.find_sent_thread_id(
                    spec,
                    token,
                    hole.message_id,
                    timeout_s=TIMEOUT_S,
                    project_id=self._project_id,
                )
                break
            except gmail_api.GmailApiFailure as error:
                self._log.info(
                    "backfill.backoff",
                    account=account.id,
                    delay_s=delay,
                    cause=error.code,
                    detail=str(error),
                )
                if index == len(BACKOFF_STEPS) - 1 or error.auth:
                    return Outcome("backoff" if not error.auth else "skipped")
                time.sleep(delay)
        thread_ids = {ref.thread_id for ref in page.messages if ref.thread_id}
        if len(thread_ids) == 1 and page.next_page_token is None:
            return self.write(account, hole, thread_ids.pop(), medium="api")
        if len(thread_ids) > 1:
            self._log.info("backfill.ambiguous", attempt=hole.attempt_id)
        return self._strike(account, hole)

    def _strike(self, account: Account, hole: ThreadHole) -> Outcome:
        state = self._attempts.miss_thread(
            hole.attempt_id, retry_after_days=self._retry_after_days
        )
        if state == "missing":
            self._log.info(
                "backfill.missing",
                attempt=hole.attempt_id,
                account=account.id,
                strikes=2,
            )
        return Outcome(state if state in {"first", "waiting", "missing"} else "skipped")
