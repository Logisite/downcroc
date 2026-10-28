from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from downcroc.domain.activity import BatchCounters
from downcroc.runtime.clock import utc_now
from downcroc.store.db.models import BatchCounterRow


def _to_counters(row: BatchCounterRow) -> BatchCounters:
    return BatchCounters(
        batch_id=row.batch_id,
        queued=row.queued,
        sent=row.sent,
        failed=row.failed,
        suppressed=row.suppressed,
        invalid=row.invalid,
        inbound=row.inbound,
        replies=row.replies,
        late_replies=row.late_replies,
        bounces=row.bounces,
        updated_at=row.updated_at,
    )


class BatchCounterRepo:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def get(self, batch_id: str) -> BatchCounters | None:
        with self._sessions() as session:
            row = session.get(BatchCounterRow, batch_id)
            return None if row is None else _to_counters(row)

    def replace(
        self,
        batch_id: str,
        *,
        queued: int,
        sent: int,
        failed: int,
        suppressed: int,
        invalid: int,
        inbound: int,
        replies: int,
        late_replies: int,
        bounces: int,
        updated_at: str | None = None,
    ) -> BatchCounters:
        moment = updated_at or utc_now()
        with self._sessions.begin() as session:
            row = session.get(BatchCounterRow, batch_id)
            if row is None:
                row = BatchCounterRow(batch_id=batch_id, updated_at=moment)
                session.add(row)
            row.queued = queued
            row.sent = sent
            row.failed = failed
            row.suppressed = suppressed
            row.invalid = invalid
            row.inbound = inbound
            row.replies = replies
            row.late_replies = late_replies
            row.bounces = bounces
            row.updated_at = moment
        return _to_counters(row)

    def list(self, limit: int = 1000) -> list[BatchCounters]:
        with self._sessions() as session:
            rows = session.scalars(
                select(BatchCounterRow)
                .order_by(BatchCounterRow.updated_at.desc())
                .limit(limit)
            )
            return [_to_counters(row) for row in rows]

    def remove(self, batch_id: str) -> bool:
        with self._sessions.begin() as session:
            row = session.get(BatchCounterRow, batch_id)
            if row is None:
                return False
            session.delete(row)
            return True
