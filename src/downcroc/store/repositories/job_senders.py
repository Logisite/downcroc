from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from downcroc.domain.jobs import Job
from downcroc.runtime.clock import utc_now
from downcroc.store.db.models import JobRow
from downcroc.store.repositories.job_mapping import to_job


class JobSenderRepo:
    """Sender policy, reassignment, and selection over the jobs table."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def pinned_accounts(self, batch_id: str) -> set[str]:
        query = select(JobRow.account_id).where(
            JobRow.batch_id == batch_id,
            JobRow.sender_policy == "pinned",
            JobRow.account_id.is_not(None),
        )
        with self._sessions() as session:
            return {row for row in session.scalars(query) if row is not None}

    def set_sender(
        self,
        job_ids: list[str],
        *,
        account_id: str | None,
        policy: str,
        reset_attempts: bool = False,
    ) -> list[str]:
        if not job_ids:
            return []
        touched: set[str] = set()
        with self._sessions.begin() as session:
            rows = session.scalars(select(JobRow).where(JobRow.id.in_(job_ids)))
            for row in rows:
                row.account_id = account_id
                row.sender_policy = policy
                row.updated_at = utc_now()
                if reset_attempts:
                    _clear_attempts(row)
                touched.add(row.batch_id)
        return sorted(touched)

    def reassign(
        self,
        job_ids: list[str],
        to_account_id: str,
        *,
        reset_attempts: bool = False,
    ) -> list[str]:
        return self.set_sender(
            job_ids,
            account_id=to_account_id,
            policy="pinned",
            reset_attempts=reset_attempts,
        )

    def select(
        self,
        *,
        job_ids: list[str] | None = None,
        batch_ids: list[str] | None = None,
        account_id: str | None = None,
        states: list[str] | None = None,
        created_since: str | None = None,
        created_until: str | None = None,
        sent_since: str | None = None,
        sent_until: str | None = None,
        limit: int = 10_000,
    ) -> list[Job]:
        if job_ids:
            query = select(JobRow).where(JobRow.id.in_(job_ids))
        else:
            query = select(JobRow)
            if batch_ids:
                query = query.where(JobRow.batch_id.in_(batch_ids))
            if account_id is not None:
                query = query.where(JobRow.account_id == account_id)
            if states:
                query = query.where(JobRow.state.in_(states))
            if created_since is not None:
                query = query.where(JobRow.created_at >= created_since)
            if created_until is not None:
                query = query.where(JobRow.created_at < created_until)
            if sent_since is not None:
                query = query.where(JobRow.sent_at >= sent_since)
            if sent_until is not None:
                query = query.where(JobRow.sent_at < sent_until)
        query = query.order_by(JobRow.created_at, JobRow.id).limit(limit)
        with self._sessions() as session:
            return [to_job(row) for row in session.scalars(query)]


def _clear_attempts(row: JobRow) -> None:
    row.attempts = 0
    row.last_error_code = None
    row.last_error_message = None
    row.retryable = None
