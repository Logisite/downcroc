from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from downcroc.domain.attempts import AttemptKind, AttemptState, ConnectAttempt
from downcroc.domain.errors import AttemptNotFound
from downcroc.store.db.models import AttemptRow


def _to_attempt(row: AttemptRow) -> ConnectAttempt:
    return ConnectAttempt(
        id=row.id,
        account_id=row.account_id,
        kind=AttemptKind(row.kind),
        state=AttemptState(row.state),
        authorization_url=row.authorization_url,
        state_token=row.state_token,
        callback_port=row.callback_port,
        created_at=row.created_at,
        expires_at=row.expires_at,
        error=row.error,
    )


class AttemptRepo:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def create(self, attempt: ConnectAttempt) -> ConnectAttempt:
        row = AttemptRow(
            id=attempt.id,
            account_id=attempt.account_id,
            kind=attempt.kind.value,
            state=attempt.state.value,
            authorization_url=attempt.authorization_url,
            state_token=attempt.state_token,
            callback_port=attempt.callback_port,
            created_at=attempt.created_at,
            expires_at=attempt.expires_at,
            error=attempt.error,
        )
        with self._sessions.begin() as session:
            session.add(row)
        return attempt

    def get(self, attempt_id: str) -> ConnectAttempt:
        with self._sessions() as session:
            row = session.get(AttemptRow, attempt_id)
            if row is None:
                raise AttemptNotFound(f"no attempt {attempt_id}")
            return _to_attempt(row)

    def pending_for_account(self, account_id: str) -> ConnectAttempt | None:
        with self._sessions() as session:
            row = session.scalar(
                select(AttemptRow)
                .where(
                    AttemptRow.account_id == account_id,
                    AttemptRow.state == AttemptState.PENDING.value,
                )
                .order_by(AttemptRow.created_at.desc())
                .limit(1)
            )
            return _to_attempt(row) if row is not None else None

    def set_state(
        self,
        attempt_id: str,
        state: AttemptState,
        error: str | None = None,
    ) -> bool:
        with self._sessions.begin() as session:
            row = session.get(AttemptRow, attempt_id)
            if row is None:
                raise AttemptNotFound(f"no attempt {attempt_id}")
            if row.state != AttemptState.PENDING.value:
                return False
            row.state = state.value
            row.error = error
            return True

    def expire_pending(self, error: str) -> int:
        with self._sessions.begin() as session:
            result = session.execute(
                update(AttemptRow)
                .where(AttemptRow.state == AttemptState.PENDING.value)
                .values(state=AttemptState.EXPIRED.value, error=error)
            )
            return result.rowcount
