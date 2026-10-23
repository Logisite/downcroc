from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from downcroc.domain.errors import JobNotFound
from downcroc.domain.jobs import Job, JobState, NewJob
from downcroc.runtime.clock import utc_now
from downcroc.store.db.models import JobRow

_SENDABLE = (JobState.QUEUED.value, JobState.RETRY_WAIT.value)


def _to_job(row: JobRow) -> Job:
    return Job(
        id=row.id,
        batch_id=row.batch_id,
        account_id=row.account_id,
        recipient=row.recipient,
        recipient_name=row.recipient_name,
        vars_json=row.vars_json,
        subject=row.subject,
        body_ref=row.body_ref,
        state=JobState(row.state),
        attempts=row.attempts,
        next_attempt_at=row.next_attempt_at,
        lease_owner=row.lease_owner,
        lease_expires_at=row.lease_expires_at,
        message_id=row.message_id,
        last_error_code=row.last_error_code,
        last_error_message=row.last_error_message,
        retryable=row.retryable,
        created_at=row.created_at,
        updated_at=row.updated_at,
        sent_at=row.sent_at,
    )


class JobRepo:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def create(self, job: NewJob) -> Job:
        row = JobRow(
            id=job.id,
            batch_id=job.batch_id,
            account_id=job.account_id,
            recipient=job.recipient,
            recipient_name=job.recipient_name,
            vars_json=job.vars_json,
            subject=job.subject,
            body_ref=job.body_ref,
            state=JobState.QUEUED.value,
            attempts=0,
            next_attempt_at=None,
            lease_owner=None,
            lease_expires_at=None,
            message_id=job.message_id,
            last_error_code=None,
            last_error_message=None,
            retryable=None,
            created_at=job.created_at,
            updated_at=job.created_at,
            sent_at=None,
        )
        with self._sessions.begin() as session:
            session.add(row)
        return self.get(job.id)

    def get(self, job_id: str) -> Job:
        with self._sessions() as session:
            row = session.get(JobRow, job_id)
            if row is None:
                raise JobNotFound(f"no job {job_id}")
            return _to_job(row)

    def list(
        self,
        *,
        batch_id: str | None = None,
        account_id: str | None = None,
        state: str | None = None,
        limit: int = 100,
    ) -> list[Job]:
        query = select(JobRow)
        if batch_id is not None:
            query = query.where(JobRow.batch_id == batch_id)
        if account_id is not None:
            query = query.where(JobRow.account_id == account_id)
        if state is not None:
            query = query.where(JobRow.state == state)
        query = query.order_by(JobRow.created_at, JobRow.id).limit(limit)
        with self._sessions() as session:
            return [_to_job(row) for row in session.scalars(query)]

    def message_id_exists(self, message_id: str) -> bool:
        with self._sessions() as session:
            row = session.scalar(
                select(JobRow.id).where(JobRow.message_id == message_id).limit(1)
            )
            return row is not None

    def claim(
        self,
        job_id: str,
        owner: str,
        now: str,
        lease_expires_at: str,
    ) -> Job | None:
        with self._sessions.begin() as session:
            row = session.get(JobRow, job_id)
            if row is None:
                raise JobNotFound(f"no job {job_id}")
            if row.state not in _SENDABLE:
                return None
            if row.lease_expires_at is not None and row.lease_expires_at > now:
                return None
            row.state = JobState.SENDING.value
            row.attempts += 1
            row.lease_owner = owner
            row.lease_expires_at = lease_expires_at
            row.updated_at = now
            row.last_error_code = None
            row.last_error_message = None
            row.retryable = None
        return self.get(job_id)

    def mark_sent(self, job_id: str, sent_at: str) -> Job:
        with self._sessions.begin() as session:
            row = self._row(session, job_id)
            row.state = JobState.SENT.value
            row.sent_at = sent_at
            row.updated_at = sent_at
            row.lease_owner = None
            row.lease_expires_at = None
            row.next_attempt_at = None
            row.last_error_code = None
            row.last_error_message = None
            row.retryable = None
        return self.get(job_id)

    def mark_reconciled(self, job_id: str, sent_at: str) -> Job:
        return self.mark_sent(job_id, sent_at)

    def mark_retry(
        self,
        job_id: str,
        *,
        code: str,
        message: str,
        next_attempt_at: str,
        retryable: bool,
    ) -> Job:
        with self._sessions.begin() as session:
            row = self._row(session, job_id)
            row.state = JobState.RETRY_WAIT.value
            row.next_attempt_at = next_attempt_at
            row.lease_owner = None
            row.lease_expires_at = None
            row.last_error_code = code
            row.last_error_message = message
            row.retryable = retryable
            row.updated_at = utc_now()
        return self.get(job_id)

    def mark_failed(
        self,
        job_id: str,
        *,
        code: str,
        message: str,
        retryable: bool,
    ) -> Job:
        with self._sessions.begin() as session:
            row = self._row(session, job_id)
            row.state = JobState.FAILED.value
            row.next_attempt_at = None
            row.lease_owner = None
            row.lease_expires_at = None
            row.last_error_code = code
            row.last_error_message = message
            row.retryable = retryable
            row.updated_at = utc_now()
        return self.get(job_id)

    def mark_queued(
        self,
        job_id: str,
        *,
        code: str | None = None,
        message: str | None = None,
        retryable: bool | None = None,
    ) -> Job:
        with self._sessions.begin() as session:
            row = self._row(session, job_id)
            row.state = JobState.QUEUED.value
            row.next_attempt_at = None
            row.lease_owner = None
            row.lease_expires_at = None
            row.last_error_code = code
            row.last_error_message = message
            row.retryable = retryable
            row.updated_at = utc_now()
        return self.get(job_id)

    def list_sending(self) -> list[Job]:
        with self._sessions() as session:
            rows = session.scalars(
                select(JobRow).where(JobRow.state == JobState.SENDING.value)
            )
            return [_to_job(row) for row in rows]

    def _row(self, session: Session, job_id: str) -> JobRow:
        row = session.get(JobRow, job_id)
        if row is None:
            raise JobNotFound(f"no job {job_id}")
        return row
