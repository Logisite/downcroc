from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session, sessionmaker

from downcroc.store.db.models import QuotaBucketRow


class QuotaRepo:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def status(self, account_id: str, day: str) -> tuple[int, int]:
        with self._sessions() as session:
            row = session.execute(
                select(QuotaBucketRow.used, QuotaBucketRow.reserved).where(
                    QuotaBucketRow.account_id == account_id,
                    QuotaBucketRow.day == day,
                )
            ).first()
            return (int(row[0]), int(row[1])) if row is not None else (0, 0)

    def used(self, account_id: str, day: str) -> int:
        return self.status(account_id, day)[0]

    def reserved(self, account_id: str, day: str) -> int:
        return self.status(account_id, day)[1]

    def available(self, account_id: str, day: str, limit: int) -> int:
        used, reserved = self.status(account_id, day)
        return max(0, limit - used - reserved)

    def reserve(
        self,
        account_id: str,
        day: str,
        limit: int,
        *,
        force: bool = False,
    ) -> int | None:
        statement = sqlite_insert(QuotaBucketRow).values(
            account_id=account_id,
            day=day,
            used=0,
            reserved=1,
        )
        updates: dict[str, object] = {"reserved": QuotaBucketRow.reserved + 1}
        conflict: dict[str, object] = {
            "index_elements": [QuotaBucketRow.account_id, QuotaBucketRow.day],
            "set_": updates,
        }
        if not force:
            conflict["where"] = QuotaBucketRow.used + QuotaBucketRow.reserved < limit
        statement = statement.on_conflict_do_update(**conflict).returning(
            QuotaBucketRow.used + QuotaBucketRow.reserved
        )
        with self._sessions.begin() as session:
            return session.scalar(statement)

    def commit(self, account_id: str, day: str) -> int:
        statement = (
            update(QuotaBucketRow)
            .where(
                QuotaBucketRow.account_id == account_id,
                QuotaBucketRow.day == day,
            )
            .values(
                used=QuotaBucketRow.used + 1,
                reserved=func.max(QuotaBucketRow.reserved - 1, 0),
            )
            .returning(QuotaBucketRow.used)
        )
        with self._sessions.begin() as session:
            used = session.scalar(statement)
            if used is not None:
                return int(used)
            session.add(
                QuotaBucketRow(account_id=account_id, day=day, used=1, reserved=0)
            )
            return 1

    def release(self, account_id: str, day: str) -> None:
        statement = (
            update(QuotaBucketRow)
            .where(
                QuotaBucketRow.account_id == account_id,
                QuotaBucketRow.day == day,
            )
            .values(reserved=func.max(QuotaBucketRow.reserved - 1, 0))
        )
        with self._sessions.begin() as session:
            session.execute(statement)

    def reset_reservations(self) -> int:
        statement = update(QuotaBucketRow).values(reserved=0)
        with self._sessions.begin() as session:
            result = session.execute(statement)
            return int(result.rowcount or 0)
