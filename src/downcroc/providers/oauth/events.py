from __future__ import annotations

from downcroc.domain.attempts import ConnectAttempt
from downcroc.runtime.logging.setup import EventLogger


def cancelled(log: EventLogger, attempt: ConnectAttempt, cause: str) -> None:
    log.info(
        "oauth.cancelled",
        attempt=attempt.id,
        account=attempt.account_id,
        cause=cause,
    )


def expired(log: EventLogger, attempt: ConnectAttempt, reason: str) -> None:
    log.warning(
        "oauth.expired",
        attempt=attempt.id,
        account=attempt.account_id,
        reason=reason,
    )
