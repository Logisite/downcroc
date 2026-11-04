from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from downcroc.domain.attempts import SendAttempt
from downcroc.runtime.clock import utc_now
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

    def create_reserved(
        self,
        attempt_id: str,
        job_id: str,
        account_id: str,
        day: str,
        started_at: str,
    ) -> None:
        with self._sessions.begin() as session:
            session.add(
                SendAttemptRow(
                    id=attempt_id,
                    job_id=job_id,
                    account_id=account_id,
                    binding_id=None,
                    transport="pending",
                    started_at=started_at,
                    finished_at=None,
                    outcome="reserved",
                    accepted=None,
                    error_code=None,
                    error_message=None,
                    provider_message_id=None,
                    detail=None,
                    quota_day=day,
                    quota_state="reserved",
                )
            )

    def finish(
        self,
        attempt_id: str,
        *,
        binding_id: str | None,
        transport: str,
        outcome: str,
        accepted: bool | None,
        code: str | None,
        message: str | None,
        provider_message_id: str | None,
    ) -> None:
        with self._sessions.begin() as session:
            row = session.get(SendAttemptRow, attempt_id)
            if row is None:
                return
            row.binding_id = binding_id
            row.transport = transport
            row.outcome = outcome
            row.accepted = accepted
            row.error_code = code
            row.error_message = message
            row.provider_message_id = provider_message_id
            row.finished_at = utc_now()

    def reserved_accepted(self) -> list[SendAttempt]:
        with self._sessions() as session:
            rows = session.scalars(
                select(SendAttemptRow)
                .where(SendAttemptRow.quota_state == "reserved")
                .where(
                    SendAttemptRow.outcome.in_(
                        ("sent", "sent_unconfirmed", "uncertain")
                    )
                )
            )
            return [_to_attempt(row) for row in rows]

    def attribution(self) -> dict[str, str]:
        """Map job id to the account of its latest attributed attempt.

        Auto-routed jobs deliberately keep ``account_id`` empty on the job row,
        so the account that actually carried the message only exists here.
        """
        with self._sessions() as session:
            rows = session.execute(
                select(
                    SendAttemptRow.job_id,
                    SendAttemptRow.account_id,
                )
                .where(SendAttemptRow.account_id.is_not(None))
                .order_by(SendAttemptRow.started_at, SendAttemptRow.id)
            )
            return {row[0]: row[1] for row in rows}

    def latest_for_job(self, job_id: str) -> SendAttempt | None:
        with self._sessions() as session:
            row = session.scalars(
                select(SendAttemptRow)
                .where(SendAttemptRow.job_id == job_id)
                .order_by(SendAttemptRow.started_at.desc(), SendAttemptRow.id.desc())
                .limit(1)
            ).first()
            return None if row is None else _to_attempt(row)

    def quota_state(self, attempt_id: str) -> str | None:
        with self._sessions() as session:
            row = session.get(SendAttemptRow, attempt_id)
            return None if row is None else row.quota_state

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
