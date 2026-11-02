from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from downcroc.domain.runtime import RuntimeState
from downcroc.runtime.clock import utc_now
from downcroc.store.db.models import RuntimeStateRow


def _state(row: RuntimeStateRow) -> RuntimeState:
    return RuntimeState(
        sending_paused_at=row.sending_paused_at,
        sending_paused_until=row.sending_paused_until,
        sending_paused_reason=row.sending_paused_reason,
        updated_at=row.updated_at,
    )


class RuntimeStateRepo:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def get(self) -> RuntimeState:
        with self._sessions.begin() as session:
            row = session.get(RuntimeStateRow, 1)
            if row is None:
                row = RuntimeStateRow(id=1, updated_at=utc_now())
                session.add(row)
                session.flush()
            return _state(row)

    def pause(
        self,
        paused_at: str,
        until: str | None,
        reason: str | None,
    ) -> RuntimeState:
        with self._sessions.begin() as session:
            row = self._row(session)
            if row.sending_paused_at is None:
                row.sending_paused_at = paused_at
                row.sending_paused_reason = reason
            elif reason is not None:
                row.sending_paused_reason = reason
            if until is not None:
                row.sending_paused_until = until
            row.updated_at = paused_at
            return _state(row)

    def resume(self) -> RuntimeState:
        with self._sessions.begin() as session:
            row = self._row(session)
            row.sending_paused_at = None
            row.sending_paused_until = None
            row.sending_paused_reason = None
            row.updated_at = utc_now()
            return _state(row)

    def clear_expired(self, now: str) -> RuntimeState | None:
        with self._sessions.begin() as session:
            row = self._row(session)
            if (
                row.sending_paused_at is None
                or row.sending_paused_until is None
                or row.sending_paused_until > now
            ):
                return None
            row.sending_paused_at = None
            row.sending_paused_until = None
            row.sending_paused_reason = None
            row.updated_at = now
            return _state(row)

    def _row(self, session: Session) -> RuntimeStateRow:
        row = session.get(RuntimeStateRow, 1)
        if row is None:
            row = RuntimeStateRow(id=1, updated_at=utc_now())
            session.add(row)
            session.flush()
        return row
