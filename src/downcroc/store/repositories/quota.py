from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session, sessionmaker

from downcroc.store.db.models import QuotaBucketRow


class QuotaRepo:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def used(self, account_id: str, day: str) -> int:
        with self._sessions() as session:
            value = session.scalar(
                select(QuotaBucketRow.used).where(
                    QuotaBucketRow.account_id == account_id,
                    QuotaBucketRow.day == day,
                )
            )
            return int(value or 0)

    def consume(self, account_id: str, day: str, limit: int) -> int | None:
        statement = sqlite_insert(QuotaBucketRow).values(
            account_id=account_id,
            day=day,
            used=1,
        )
        statement = statement.on_conflict_do_update(
            index_elements=[QuotaBucketRow.account_id, QuotaBucketRow.day],
            set_={"used": QuotaBucketRow.used + 1},
            where=QuotaBucketRow.used < limit,
        ).returning(QuotaBucketRow.used)
        with self._sessions.begin() as session:
            return session.scalar(statement)
