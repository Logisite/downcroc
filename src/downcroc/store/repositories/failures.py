from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session, sessionmaker

from downcroc.domain.errors import FailureNotFound
from downcroc.domain.failures import FailedJob
from downcroc.store.db.models import FailedJobRow, JobRow


def _to_failure(row: FailedJobRow) -> FailedJob:
    return FailedJob(
        job_id=row.job_id,
        batch_id=row.batch_id,
        account_id=row.account_id,
        recipient=row.recipient,
        code=row.code,
        message=row.message,
        retryable=row.retryable,
        attempts=row.attempts,
        failed_at=row.failed_at,
    )


class FailureRepo:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def add(self, failure: FailedJob) -> bool:
        statement = (
            sqlite_insert(FailedJobRow)
            .values(
                job_id=failure.job_id,
                batch_id=failure.batch_id,
                account_id=failure.account_id,
                recipient=failure.recipient,
                code=failure.code,
                message=failure.message,
                retryable=failure.retryable,
                attempts=failure.attempts,
                failed_at=failure.failed_at,
            )
            .on_conflict_do_nothing(index_elements=["job_id"])
        )
        with self._sessions.begin() as session:
            result = session.execute(statement)
            return result.rowcount > 0

    def exists(self, job_id: str) -> bool:
        with self._sessions() as session:
            found = session.scalar(
                select(FailedJobRow.job_id)
                .where(FailedJobRow.job_id == job_id)
                .limit(1)
            )
            return found is not None

    def get(self, job_id: str) -> FailedJob:
        with self._sessions() as session:
            row = session.get(FailedJobRow, job_id)
            if row is None:
                raise FailureNotFound(f"no failure for job {job_id}")
            return _to_failure(row)

    def list(self, limit: int = 100, offset: int = 0) -> list[FailedJob]:
        query = (
            select(FailedJobRow)
            .order_by(FailedJobRow.failed_at.desc(), FailedJobRow.job_id)
            .offset(offset)
            .limit(limit)
        )
        with self._sessions() as session:
            return [_to_failure(row) for row in session.scalars(query)]

    def count(self) -> int:
        with self._sessions() as session:
            return int(
                session.scalar(select(func.count()).select_from(FailedJobRow)) or 0
            )

    def remove(self, job_id: str) -> bool:
        with self._sessions.begin() as session:
            row = session.get(FailedJobRow, job_id)
            if row is None:
                return False
            session.delete(row)
            return True

    def matching(
        self,
        *,
        states: list[str] | None = None,
        older_than: str | None = None,
    ) -> list[FailedJob]:
        query = select(FailedJobRow)
        if states:
            query = query.where(
                FailedJobRow.job_id.in_(
                    select(JobRow.id).where(JobRow.state.in_(states))
                )
            )
        if older_than is not None:
            query = query.where(FailedJobRow.failed_at < older_than)
        with self._sessions() as session:
            return [_to_failure(row) for row in session.scalars(query)]

    def remove_many(self, job_ids: list[str]) -> int:
        if not job_ids:
            return 0
        with self._sessions.begin() as session:
            result = session.execute(
                delete(FailedJobRow).where(FailedJobRow.job_id.in_(job_ids))
            )
            return int(result.rowcount or 0)
