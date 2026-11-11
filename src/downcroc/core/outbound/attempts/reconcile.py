from __future__ import annotations

from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.repositories.send_attempts import SendAttemptRepo


def reconcile_interrupted(attempts: SendAttemptRepo, log: EventLogger) -> int:
    count = attempts.reconcile_interrupted()
    if count:
        log.warning("send_attempts.reconciled", count=count)
    return count
