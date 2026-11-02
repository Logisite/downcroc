from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from downcroc.domain.attempts import SendAttempt
from downcroc.store.db.models import SendAttemptRow


def _to_attempt(row: SendAttemptRow) -> SendAttempt:
    return SendAttempt(
        id=row.id,
        job_id=row.job_id,
        account_id=row.account_id,
        binding_id=row.binding_id,
        transport=row.transport,
        started_at=row.started_at,
        finished_at=row.finished_at,
        outcome=row.outcome,
        accepted=row.accepted,
        error_code=row.error_code,
        error_message=row.error_message,
        provider_message_id=row.provider_message_id,
        detail=row.detail,
        quota_day=row.quota_day,
        quota_state=row.quota_state,
    )


class SendAttemptRepo:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def create(self, attempt: SendAttempt) -> SendAttempt:
        row = SendAttemptRow(
            id=attempt.id,
            job_id=attempt.job_id,
            account_id=attempt.account_id,
            binding_id=attempt.binding_id,
            transport=attempt.transport,
            started_at=attempt.started_at,
            finished_at=attempt.finished_at,
            outcome=attempt.outcome,
            accepted=attempt.accepted,
            error_code=attempt.error_code,
            error_message=attempt.error_message,
            provider_message_id=attempt.provider_message_id,
            detail=attempt.detail,
            quota_day=attempt.quota_day,
            quota_state=attempt.quota_state,
        )
        with self._sessions.begin() as session:
            session.add(row)
        return attempt

    def latest_for_job(self, job_id: str) -> SendAttempt | None:
        with self._sessions() as session:
            row = session.scalars(
                select(SendAttemptRow)
                .where(SendAttemptRow.job_id == job_id)
                .order_by(SendAttemptRow.started_at.desc(), SendAttemptRow.id.desc())
                .limit(1)
            ).first()
            return None if row is None else _to_attempt(row)

    def set_quota(self, attempt_id: str, day: str, state: str) -> None:
        with self._sessions.begin() as session:
            session.execute(
                update(SendAttemptRow)
                .where(SendAttemptRow.id == attempt_id)
                .values(quota_day=day, quota_state=state)
            )

    def release_reserved(self) -> int:
        with self._sessions.begin() as session:
            result = session.execute(
                update(SendAttemptRow)
                .where(SendAttemptRow.quota_state == "reserved")
                .values(quota_state="released")
            )
            return int(result.rowcount or 0)

    def list_for_job(self, job_id: str) -> list[SendAttempt]:
        with self._sessions() as session:
            rows = session.scalars(
                select(SendAttemptRow)
                .where(SendAttemptRow.job_id == job_id)
                .order_by(SendAttemptRow.started_at, SendAttemptRow.id)
            )
            return [_to_attempt(row) for row in rows]
