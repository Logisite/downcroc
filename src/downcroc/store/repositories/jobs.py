from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from downcroc.domain.errors import JobNotFound
from downcroc.domain.jobs import Job, JobState, NewJob
from downcroc.runtime.clock import utc_now
from downcroc.store.db.models import JobRow
from downcroc.store.repositories.job_mapping import to_job, to_row

_SENDABLE = (JobState.QUEUED.value, JobState.RETRY_WAIT.value)


class JobRepo:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def create(self, job: NewJob) -> Job:
        with self._sessions.begin() as session:
            session.add(to_row(job))
        return self.get(job.id)

    def create_many(self, jobs: list[NewJob]) -> None:
        if not jobs:
            return
        with self._sessions.begin() as session:
            session.add_all([to_row(job) for job in jobs])

    def get(self, job_id: str) -> Job:
        with self._sessions() as session:
            row = session.get(JobRow, job_id)
            if row is None:
                raise JobNotFound(f"no job {job_id}")
            return to_job(row)

    def list(
        self,
        *,
        batch_id: str | None = None,
        account_id: str | None = None,
        state: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Job]:
        query = self._filtered(batch_id, account_id, state)
        query = query.order_by(JobRow.created_at, JobRow.id).offset(offset).limit(limit)
        with self._sessions() as session:
            return [to_job(row) for row in session.scalars(query)]

    def count(
        self,
        *,
        batch_id: str | None = None,
        account_id: str | None = None,
        state: str | None = None,
    ) -> int:
        query = self._filtered(batch_id, account_id, state)
        count = select(func.count()).select_from(query.subquery())
        with self._sessions() as session:
            return int(session.scalar(count) or 0)

    @staticmethod
    def _filtered(
        batch_id: str | None,
        account_id: str | None,
        state: str | None,
    ):
        query = select(JobRow)
        if batch_id is not None:
            query = query.where(JobRow.batch_id == batch_id)
        if account_id is not None:
            query = query.where(JobRow.account_id == account_id)
        if state is not None:
            query = query.where(JobRow.state == state)
        return query

    def thread_jobs(self, thread_root_job_id: str) -> list[Job]:
        return self.thread_jobs_many([thread_root_job_id]).get(thread_root_job_id, [])

    def thread_jobs_many(self, root_ids: list[str]) -> dict[str, list[Job]]:
        if not root_ids:
            return {}
        with self._sessions() as session:
            rows = session.scalars(
                select(JobRow)
                .where(JobRow.thread_root_job_id.in_(root_ids))
                .order_by(JobRow.created_at, JobRow.id)
            )
            grouped: dict[str, list[Job]] = {}
            for row in rows:
                grouped.setdefault(row.thread_root_job_id or "", []).append(to_job(row))
            return grouped

    def pending_followups(self, limit: int = 1000) -> list[Job]:
        active = (
            JobState.QUEUED.value,
            JobState.AWAITING_APPROVAL.value,
            JobState.RETRY_WAIT.value,
        )
        with self._sessions() as session:
            rows = session.scalars(
                select(JobRow)
                .where(JobRow.step_key.is_not(None), JobRow.state.in_(active))
                .order_by(JobRow.created_at, JobRow.id)
                .limit(limit)
            )
            return [to_job(row) for row in rows]

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

    def set_state(self, job_id: str, state: JobState) -> Job:
        with self._sessions.begin() as session:
            row = self._row(session, job_id)
            row.state = state.value
            row.updated_at = utc_now()
        return self.get(job_id)

    def list_sending(self) -> list[Job]:
        with self._sessions() as session:
            rows = session.scalars(
                select(JobRow).where(JobRow.state == JobState.SENDING.value)
            )
            return [to_job(row) for row in rows]

    def due(self, account_id: str, now: str, limit: int = 50) -> list[Job]:
        sendable = JobRow.state.in_(_SENDABLE) & (
            (JobRow.next_attempt_at.is_(None)) | (JobRow.next_attempt_at <= now)
        )
        expired = (JobRow.state == JobState.SENDING.value) & (
            JobRow.lease_expires_at.is_(None) | (JobRow.lease_expires_at <= now)
        )
        query = (
            select(JobRow)
            .where(JobRow.account_id == account_id, sendable | expired)
            .order_by(
                func.coalesce(JobRow.next_attempt_at, JobRow.created_at),
                JobRow.created_at,
                JobRow.id,
            )
            .limit(limit)
        )
        with self._sessions() as session:
            return [to_job(row) for row in session.scalars(query)]

    def reset_for_retry(self, job_id: str) -> Job:
        with self._sessions.begin() as session:
            row = self._row(session, job_id)
            row.state = JobState.QUEUED.value
            row.attempts = 0
            row.next_attempt_at = None
            row.lease_owner = None
            row.lease_expires_at = None
            row.last_error_code = None
            row.last_error_message = None
            row.retryable = None
            row.updated_at = utc_now()
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

    def counts(self, batch_id: str) -> dict[str, int]:
        with self._sessions() as session:
            rows = session.execute(
                select(JobRow.state, func.count())
                .where(JobRow.batch_id == batch_id)
                .group_by(JobRow.state)
            )
            return {state: count for state, count in rows}

    def activity_rows(self) -> list[tuple[str, str | None, str | None, str]]:
        with self._sessions() as session:
            rows = session.execute(
                select(
                    JobRow.account_id,
                    JobRow.sent_at,
                    JobRow.updated_at,
                    JobRow.state,
                )
            )
            return [(row[0], row[1], row[2], row[3]) for row in rows]

    def prunable(self, cutoff: str, keep: int) -> list[Job]:
        terminal = (
            JobState.SENT.value,
            JobState.SENT_UNCONFIRMED.value,
            JobState.FAILED.value,
            JobState.CANCELLED.value,
        )
        with self._sessions() as session:
            rows = list(
                session.scalars(
                    select(JobRow)
                    .where(JobRow.state.in_(terminal))
                    .order_by(
                        func.coalesce(JobRow.sent_at, JobRow.updated_at),
                        JobRow.id,
                    )
                )
            )
            total = len(rows)
            chosen = [
                to_job(row)
                for index, row in enumerate(rows)
                if total - index > keep or (row.sent_at or row.updated_at) < cutoff
            ]
            return chosen

    def delete_many(self, job_ids: list[str]) -> int:
        if not job_ids:
            return 0
        with self._sessions.begin() as session:
            result = session.execute(delete(JobRow).where(JobRow.id.in_(job_ids)))
            return int(result.rowcount or 0)

    def ids_in_states(self, batch_id: str, states: tuple[JobState, ...]) -> list[str]:
        wanted = tuple(state.value for state in states)
        with self._sessions() as session:
            rows = session.scalars(
                select(JobRow.id)
                .where(JobRow.batch_id == batch_id, JobRow.state.in_(wanted))
                .order_by(JobRow.created_at, JobRow.id)
            )
            return list(rows)

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

    def _row(self, session: Session, job_id: str) -> JobRow:
        row = session.get(JobRow, job_id)
        if row is None:
            raise JobNotFound(f"no job {job_id}")
        return row
