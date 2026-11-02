from __future__ import annotations

import json
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from downcroc.domain.events import Event
from downcroc.runtime.clock import utc_now
from downcroc.store.db.models import EventRow


def _to_event(row: EventRow) -> Event:
    return Event(
        seq=row.seq,
        type=row.type,
        ts=row.ts,
        data=json_loads(row.payload_json),
    )


class EventRepo:
    def __init__(self, sessions: sessionmaker[Session], ring_size: int) -> None:
        self._sessions = sessions
        self._ring_size = ring_size

    def append(self, event_type: str, data: dict[str, Any]) -> Event:
        ts = utc_now()
        payload = json_dumps(data)
        with self._sessions.begin() as session:
            row = EventRow(type=event_type, ts=ts, payload_json=payload)
            session.add(row)
            session.flush()
            session.execute(
                delete(EventRow).where(EventRow.seq <= row.seq - self._ring_size)
            )
            seq = row.seq
        return Event(seq=seq, type=event_type, ts=ts, data=data)

    def after(self, seq: int, limit: int) -> list[Event]:
        with self._sessions() as session:
            rows = session.scalars(
                select(EventRow)
                .where(EventRow.seq > seq)
                .order_by(EventRow.seq)
                .limit(limit)
            ).all()
            return [_to_event(row) for row in rows]

    def recent(self, prefix: str, limit: int) -> list[Event]:
        """Return the newest events whose type starts with ``prefix``.

        The result is chronological so a caller can render a timeline without
        reversing it again.
        """
        with self._sessions() as session:
            rows = session.scalars(
                select(EventRow)
                .where(EventRow.type.like(f"{prefix}%"))
                .order_by(EventRow.seq.desc())
                .limit(limit)
            ).all()
            return [_to_event(row) for row in reversed(rows)]

    def bounds(self) -> tuple[int | None, int | None]:
        with self._sessions() as session:
            oldest, newest = session.execute(
                select(func.min(EventRow.seq), func.max(EventRow.seq))
            ).one()
            return oldest, newest


def json_dumps(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def json_loads(payload: str) -> dict[str, Any]:
    return json.loads(payload)
