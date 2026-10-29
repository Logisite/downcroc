from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from downcroc.domain.errors import JobNotFound
from downcroc.domain.jobs import Job, JobState
from downcroc.runtime.clock import utc_now
from downcroc.store.db.models import JobRow
from downcroc.store.repositories.job_mapping import to_job

_SENDABLE = (JobState.QUEUED.value, JobState.RETRY_WAIT.value)


class JobStateRepo:
    """Job lease, state transitions, and retry bookkeeping."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

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
            expired = row.lease_expires_at is None or row.lease_expires_at <= now
            if row.state == JobState.SENDING.value and not expired:
                return None
            if row.state not in _SENDABLE and row.state != JobState.SENDING.value:
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
            _release(row)
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
            _release(row)
            _error(row, code, message, retryable)
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
            _release(row)
            _error(row, code, message, retryable)
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
            _release(row)
            _error(row, code, message, retryable)
        return self.get(job_id)

    def set_state(self, job_id: str, state: JobState) -> Job:
        with self._sessions.begin() as session:
            row = self._row(session, job_id)
            row.state = state.value
            row.updated_at = utc_now()
        return self.get(job_id)

    def reset_for_retry(self, job_id: str) -> Job:
        with self._sessions.begin() as session:
            row = self._row(session, job_id)
            row.state = JobState.QUEUED.value
            row.attempts = 0
            row.next_attempt_at = None
            _release(row)
            _error(row, None, None, None)
        return self.get(job_id)

    def transition_one(
        self,
        job_id: str,
        *,
        from_state: JobState,
        to_state: JobState,
    ) -> Job | None:
        with self._sessions.begin() as session:
            row = session.get(JobRow, job_id)
            if row is None:
                raise JobNotFound(f"no job {job_id}")
            if row.state != from_state.value:
                return None
            row.state = to_state.value
            row.updated_at = utc_now()
        return self.get(job_id)

    def transition_batch(
        self,
        batch_id: str,
        *,
        from_states: tuple[JobState, ...],
        to_state: JobState,
    ) -> int:
        wanted = tuple(state.value for state in from_states)
        with self._sessions.begin() as session:
            rows = session.scalars(
                select(JobRow).where(
                    JobRow.batch_id == batch_id, JobRow.state.in_(wanted)
                )
            )
            changed = 0
            for row in rows:
                row.state = to_state.value
                row.updated_at = utc_now()
                changed += 1
            return changed

    def list_sending(self) -> list[Job]:
        with self._sessions() as session:
            rows = session.scalars(
                select(JobRow).where(JobRow.state == JobState.SENDING.value)
            )
            return [to_job(row) for row in rows]


def _release(row: JobRow) -> None:
    row.lease_owner = None
    row.lease_expires_at = None


def _error(
    row: JobRow,
    code: str | None,
    message: str | None,
    retryable: bool | None,
) -> None:
    row.last_error_code = code
    row.last_error_message = message
    row.retryable = retryable
    row.updated_at = utc_now()
