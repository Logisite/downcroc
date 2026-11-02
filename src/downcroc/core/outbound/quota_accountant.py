from __future__ import annotations

import traceback

from downcroc.core.events import EventBus
from downcroc.domain.accounts import Account
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.repositories.quota import QuotaRepo
from downcroc.store.repositories.send_attempts import SendAttemptRepo


class QuotaAccountant:
    """Reserve, commit, and release one attempt's daily allowance unit."""

    def __init__(
        self,
        quota: QuotaRepo,
        attempts: SendAttemptRepo,
        bus: EventBus,
        log: EventLogger,
    ) -> None:
        self._quota = quota
        self._attempts = attempts
        self._bus = bus
        self._log = log

    def reserve(
        self,
        account: Account,
        day: str,
        limit: int,
        *,
        attempt_id: str,
        job_id: str,
        started_at: str,
        manual: bool = False,
    ) -> bool:
        reserved = self._quota.reserve(account.id, day, limit, force=manual)
        if reserved is None:
            self._log.info(
                "quota.exhausted",
                account=account.id,
                day=day,
                limit=limit,
            )
            return False
        try:
            self._attempts.create_reserved(
                attempt_id,
                job_id,
                account.id,
                day,
                started_at,
            )
        except Exception as error:
            self._log.error(
                "quota.reserve_failed",
                account=account.id,
                day=day,
                error=type(error).__name__,
                detail=str(error)[:500],
                traceback=traceback.format_exc()[-4000:],
            )
            self._quota.release(account.id, day)
            raise
        used, reserved_now = self._quota.status(account.id, day)
        self._log.info(
            "quota.reserved",
            account=account.id,
            day=day,
            used=used,
            reserved=reserved_now,
            limit=limit,
        )
        self._bus.publish(
            "quota.reserved",
            {
                "account": account.id,
                "day": day,
                "used": used,
                "reserved": reserved_now,
                "limit": limit,
            },
        )
        return True

    def commit(self, account_id: str, day: str, attempt_id: str) -> None:
        if self._attempts.quota_state(attempt_id) == "committed":
            return
        used = self._quota.commit(account_id, day)
        reserved = self._quota.reserved(account_id, day)
        self._attempts.set_quota(attempt_id, day, "committed")
        self._log.info(
            "quota.committed",
            account=account_id,
            day=day,
            used=used,
            reserved=reserved,
        )
        self._bus.publish(
            "quota.committed",
            {"account": account_id, "day": day, "used": used, "reserved": reserved},
        )

    def release(
        self,
        account_id: str,
        day: str,
        reason: str,
        attempt_id: str,
    ) -> None:
        if self._attempts.quota_state(attempt_id) in {"released", "committed"}:
            return
        self._quota.release(account_id, day)
        reserved = self._quota.reserved(account_id, day)
        self._attempts.set_quota(attempt_id, day, "released")
        self._log.info(
            "quota.released",
            account=account_id,
            day=day,
            reason=reason,
            reserved=reserved,
        )
        self._bus.publish(
            "quota.released",
            {
                "account": account_id,
                "day": day,
                "reason": reason,
                "reserved": reserved,
            },
        )
