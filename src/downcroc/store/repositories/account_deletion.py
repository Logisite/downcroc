from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session, sessionmaker

from downcroc.domain.accounts import AccountStatus
from downcroc.domain.errors import (
    AccountArchived,
    AccountInUse,
    AccountPending,
    JobInFlight,
    ReassignSameAccount,
    ReassignTargetInvalid,
)
from downcroc.store.db.models import (
    AccountRow,
    ActivityDailyRow,
    ActivityHourlyRow,
    AttemptRow,
    BatchRow,
    JobRow,
    MessageRow,
    QuotaBucketRow,
    SendAttemptRow,
)

MOVABLE = ("queued", "awaiting_approval", "retry_wait")
UNSENT = ("queued", "awaiting_approval", "retry_wait", "failed", "cancelled")
HISTORY = ("sent", "sent_unconfirmed")


@dataclass(frozen=True)
class AccountDelete:
    account_id: str
    reassigned: int
    deleted_jobs: int
    bodies: tuple[str, ...]
    batches: tuple[str, ...]


class AccountDeletionRepo:
    """Deletion preview and account teardown, including job handover."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def deletion_counts(self, account_id: str) -> dict[str, int]:
        with self._sessions() as session:
            self._row(session, account_id)
            jobs = self._counts(session, JobRow.state, JobRow.account_id, account_id)
            pinned_jobs = sum(jobs.values())
            pinned_batches = set(
                session.scalars(
                    select(JobRow.batch_id).where(JobRow.account_id == account_id)
                )
            )
            auto_rows = session.execute(
                select(JobRow.batch_id, JobRow.sender_policy)
                .join(BatchRow, BatchRow.id == JobRow.batch_id)
                .where(BatchRow.account_id == account_id)
            )
            auto_batches = {batch for batch, _policy in auto_rows}
            auto_jobs = int(
                session.scalar(
                    select(func.count())
                    .select_from(JobRow)
                    .join(BatchRow, BatchRow.id == JobRow.batch_id)
                    .where(
                        BatchRow.account_id == account_id,
                        JobRow.sender_policy == "auto",
                    )
                )
                or 0
            )
            return {
                "jobs": pinned_jobs,
                "pinned_jobs": pinned_jobs,
                "auto_jobs": auto_jobs,
                "queued": jobs.get("queued", 0),
                "awaiting_approval": jobs.get("awaiting_approval", 0),
                "retry_wait": jobs.get("retry_wait", 0),
                "sending": jobs.get("sending", 0),
                "sent": jobs.get("sent", 0) + jobs.get("sent_unconfirmed", 0),
                "failed": jobs.get("failed", 0),
                "cancelled": jobs.get("cancelled", 0),
                "batches": len(pinned_batches | auto_batches),
                "batches_pinned": len(pinned_batches),
                "messages": self._count(session, MessageRow, account_id),
                "attempts": self._count(session, AttemptRow, account_id),
                "send_attempts": self._count(session, SendAttemptRow, account_id),
                "activity": self._count(session, ActivityHourlyRow, account_id)
                + self._count(session, ActivityDailyRow, account_id),
                "quota": self._count(session, QuotaBucketRow, account_id),
            }

    def delete(
        self,
        account_id: str,
        *,
        reassign_to: str | None = None,
        force_jobs: bool = False,
        force_history: bool = False,
    ) -> AccountDelete:
        with self._sessions.begin() as session:
            row = self._row(session, account_id)
            jobs = list(
                session.scalars(select(JobRow).where(JobRow.account_id == account_id))
            )
            if any(job.state == "sending" for job in jobs):
                raise JobInFlight(
                    f"account {account_id} has a job in flight",
                    hint="wait for the lease to expire and retry",
                )
            if reassign_to is not None:
                return self._delete_reassigned(session, row, jobs, reassign_to)
            if not jobs:
                self._detach_batches(session, account_id)
                session.delete(row)
                return AccountDelete(account_id, 0, 0, (), ())
            if not force_jobs:
                raise AccountInUse(
                    f"account {account_id} has {len(jobs)} jobs",
                    hint=(
                        "pass --reassign-to to move the work, or --force-jobs "
                        "to delete unsent jobs"
                    ),
                )
            history = [job for job in jobs if job.state in HISTORY]
            if history and not force_history:
                raise AccountInUse(
                    f"account {account_id} has {len(history)} sent jobs",
                    hint="pass --force-history to delete sent history as well",
                )
            doomed = [
                job
                for job in jobs
                if job.state in UNSENT or (force_history and job.state in HISTORY)
            ]
            bodies = tuple(job.body_ref for job in doomed)
            batches = tuple(sorted({job.batch_id for job in doomed}))
            if doomed:
                session.execute(
                    delete(JobRow).where(JobRow.id.in_([job.id for job in doomed]))
                )
            self._detach_batches(session, account_id)
            session.delete(row)
            return AccountDelete(account_id, 0, len(doomed), bodies, batches)

    def _delete_reassigned(
        self,
        session: Session,
        row: AccountRow,
        jobs: list[JobRow],
        reassign_to: str,
    ) -> AccountDelete:
        if reassign_to == row.id:
            raise ReassignSameAccount("the source and target account are the same")
        target = session.get(AccountRow, reassign_to)
        if target is None:
            raise ReassignTargetInvalid(f"no account {reassign_to}")
        if target.archived_at is not None:
            raise AccountArchived(f"account {reassign_to} is archived")
        if target.status == AccountStatus.PENDING.value:
            raise AccountPending(
                f"account {reassign_to} is pending",
                hint="connect the target account before reassigning work to it",
            )
        moved = 0
        for job in jobs:
            if job.state in MOVABLE:
                job.account_id = reassign_to
                moved += 1
        remaining = [job for job in jobs if job.state not in MOVABLE]
        if remaining:
            raise AccountInUse(
                f"account {row.id} still has {len(remaining)} jobs",
                hint=(
                    "pass --force-jobs and --force-history to delete the "
                    "remaining history"
                ),
            )
        batches = tuple(sorted({job.batch_id for job in jobs}))
        self._repoint_batches(session, row.id, jobs, reassign_to)
        self._detach_batches(session, row.id)
        session.delete(row)
        return AccountDelete(row.id, moved, 0, (), batches)

    @staticmethod
    def _repoint_batches(
        session: Session,
        account_id: str,
        jobs: list[JobRow],
        target_id: str,
    ) -> None:
        for batch_id in {job.batch_id for job in jobs}:
            remaining = session.scalar(
                select(JobRow.id)
                .where(
                    JobRow.batch_id == batch_id,
                    JobRow.account_id == account_id,
                )
                .limit(1)
            )
            if remaining is not None:
                continue
            batch = session.get(BatchRow, batch_id)
            if batch is not None and batch.account_id == account_id:
                batch.account_id = target_id

    @staticmethod
    def _detach_batches(session: Session, account_id: str) -> None:
        session.execute(
            update(BatchRow)
            .where(BatchRow.account_id == account_id)
            .values(account_id=None)
        )

    @staticmethod
    def _count(session: Session, model, account_id: str) -> int:
        query = (
            select(func.count())
            .select_from(model)
            .where(model.account_id == account_id)
        )
        return int(session.scalar(query) or 0)

    @staticmethod
    def _counts(session: Session, column, account_column, account_id: str) -> dict:
        rows = session.execute(
            select(column, func.count())
            .where(account_column == account_id)
            .group_by(column)
        )
        return {state: count for state, count in rows}
