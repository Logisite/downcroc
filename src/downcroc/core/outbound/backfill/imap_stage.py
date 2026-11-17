from __future__ import annotations

import time

from downcroc.core.credentials import CredentialResolver
from downcroc.domain.accounts import Account
from downcroc.domain.providers import ProviderSpec
from downcroc.mail.imap.client import close, select_sent
from downcroc.mail.imap.connection import (
    ImapAuthError,
    ImapNetworkError,
    ImapProtocolError,
    ImapTlsError,
    authenticate,
    connect,
)
from downcroc.mail.imap.folders import resolve_sent_folder
from downcroc.mail.imap.sent_scan import SweepResult, has_gmail_extensions, sweep
from downcroc.runtime.logging.setup import EventLogger

TIMEOUT_S = 30.0


def lane_token(
    account: Account,
    spec: ProviderSpec,
    credentials: CredentialResolver,
    log: EventLogger,
) -> str | None:
    """Credential for one account turn; locked or broken accounts are skipped."""

    try:
        # Resolve through the credential layer so imported per-account OAuth
        # clients are overlaid before the token is requested.
        return credentials.access_token(account, spec)
    except Exception as error:  # noqa: BLE001
        _skipped(account, error, log)
        return None


def imap_sweep(
    account: Account,
    spec: ProviderSpec,
    token: str,
    *,
    chunk: int,
    pace_s: float,
    log: EventLogger,
) -> SweepResult | None:
    """Stage 1: read-only Sent sweep, or None when the account must use stage 2.

    The sweep opens its own connection, never touches the watcher's, and selects
    the Sent folder readonly with ``BODY.PEEK`` so no flag can change.
    """

    box = connect(spec, timeout_s=TIMEOUT_S)
    try:
        authenticate(box, account.address, access_token=token)
        if not has_gmail_extensions(box):
            return None
        select_sent(box, resolve_sent_folder(box, spec))
        started = time.monotonic()
        last_mark = 0

        def progress(seen: int, total: int) -> None:
            nonlocal last_mark
            if seen >= total:
                return
            mark = (seen * 100) // max(total, 1)
            if mark >= last_mark + 25:
                last_mark = mark
                log.info(
                    "backfill.imap_progress",
                    account=account.id,
                    messages=seen,
                    total=total,
                )

        result = sweep(box, chunk, pace=_pacer(pace_s), progress=progress)
        log.info(
            "backfill.imap_swept",
            account=account.id,
            messages=result.messages,
            hits=len(result.threads),
            duration_ms=round((time.monotonic() - started) * 1000),
        )
        return result
    except (ImapAuthError, ImapNetworkError, ImapProtocolError, ImapTlsError) as error:
        _skipped(account, error, log)
        return None
    finally:
        close(box)


def _pacer(pace_s: float):
    def after_chunk(count: int) -> None:
        if pace_s > 0 and count:
            time.sleep(pace_s)

    return after_chunk


def _skipped(account: Account, error: Exception, log: EventLogger) -> None:
    log.info(
        "backfill.backoff",
        account=account.id,
        delay_s=0,
        cause=error.__class__.__name__,
    )
