from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from downcroc.domain.attempts import SendAttempt
from downcroc.store.db.models import SendAttemptRow


def _to_attempt(row: SendAttemptRow) -> SendAttempt:
    return SendAttempt(
        id=row.id,
        job_id=row.job_id,
        account_id=row.account_id,
        transport=row.transport,
        started_at=row.started_at,
        finished_at=row.finished_at,
        outcome=row.outcome,
        accepted=row.accepted,
        error_code=row.error_code,
        error_message=row.error_message,
        provider_message_id=row.provider_message_id,
        detail=row.detail,
    )


class SendAttemptRepo:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def create(self, attempt: SendAttempt) -> SendAttempt:
        row = SendAttemptRow(
            id=attempt.id,
            job_id=attempt.job_id,
            account_id=attempt.account_id,
            transport=attempt.transport,
            started_at=attempt.started_at,
            finished_at=attempt.finished_at,
            outcome=attempt.outcome,
            accepted=attempt.accepted,
            error_code=attempt.error_code,
            error_message=attempt.error_message,
            provider_message_id=attempt.provider_message_id,
            detail=attempt.detail,
        )
        with self._sessions.begin() as session:
            session.add(row)
        return attempt

    def list_for_job(self, job_id: str) -> list[SendAttempt]:
        with self._sessions() as session:
            rows = session.scalars(
                select(SendAttemptRow)
                .where(SendAttemptRow.job_id == job_id)
                .order_by(SendAttemptRow.started_at, SendAttemptRow.id)
            )
            return [_to_attempt(row) for row in rows]
