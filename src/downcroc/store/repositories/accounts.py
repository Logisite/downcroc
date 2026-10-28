from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from downcroc.domain.accounts import Account, AccountStatus, SendPolicy
from downcroc.domain.errors import (
    AccountArchived,
    AccountExists,
    AccountInUse,
    AccountNotFound,
    JobInFlight,
    ReassignSameAccount,
    ReassignTargetInvalid,
)
from downcroc.store.db.models import (
    AccountRow,
    AccountStateRow,
    ActivityDailyRow,
    ActivityHourlyRow,
    AttemptRow,
    JobRow,
    MessageRow,
    QuotaBucketRow,
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


def _to_account(row: AccountRow, state: AccountStateRow | None) -> Account:
    return Account(
        id=row.id,
        provider=row.provider_id,
        address=row.address,
        label=row.label,
        status=AccountStatus(row.status),
        credential_present=row.credential_key is not None,
        created_at=row.created_at,
        last_verified_at=row.last_verified_at,
        archived_at=row.archived_at,
        policy=SendPolicy(
            daily_allowance=row.daily_allowance,
            window_start=row.window_start,
            window_end=row.window_end,
            jitter_min=row.jitter_min,
            jitter_max=row.jitter_max,
            max_in_flight=row.max_in_flight,
            enabled=row.enabled,
        ),
        last_error=state.last_error if state is not None else None,
        credential_key=row.credential_key,
        watcher_enabled=state.watcher_enabled if state is not None else True,
        last_uid=state.last_uid if state is not None else 0,
        uidvalidity=state.uidvalidity if state is not None else 0,
        last_sync_at=state.last_sync_at if state is not None else None,
        consecutive_failures=state.consecutive_failures if state is not None else 0,
    )


class AccountRepo:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def list(self, *, include_archived: bool = False) -> list[Account]:
        query = (
            select(AccountRow, AccountStateRow)
            .outerjoin(AccountStateRow, AccountStateRow.account_id == AccountRow.id)
            .order_by(AccountRow.created_at, AccountRow.id)
        )
        if not include_archived:
            query = query.where(AccountRow.archived_at.is_(None))
        with self._sessions() as session:
            rows = session.execute(query).all()
            return [_to_account(row, state) for row, state in rows]

    def get(self, account_id: str) -> Account:
        with self._sessions() as session:
            row = session.get(AccountRow, account_id)
            if row is None:
                raise AccountNotFound(f"no account {account_id}")
            state = session.get(AccountStateRow, account_id)
            return _to_account(row, state)

    def create(self, account: Account) -> Account:
        row = AccountRow(
            id=account.id,
            provider_id=account.provider,
            address=account.address,
            label=account.label,
            status=account.status.value,
            credential_key=None,
            created_at=account.created_at,
            last_verified_at=account.last_verified_at,
            daily_allowance=account.policy.daily_allowance,
            window_start=account.policy.window_start,
            window_end=account.policy.window_end,
            jitter_min=account.policy.jitter_min,
            jitter_max=account.policy.jitter_max,
            max_in_flight=account.policy.max_in_flight,
            enabled=account.policy.enabled,
        )
        try:
            with self._sessions.begin() as session:
                session.add(row)
                session.add(AccountStateRow(account_id=account.id))
        except IntegrityError as error:
            raise AccountExists(
                f"{account.address} is already added for {account.provider}"
            ) from error
        return account

    def mark_connected(
        self,
        account_id: str,
        credential_key: str,
        verified_at: str,
    ) -> Account:
        with self._sessions.begin() as session:
            row = self._row(session, account_id)
            state = self._state(session, account_id)
            row.status = AccountStatus.CONNECTED.value
            row.credential_key = credential_key
            row.last_verified_at = verified_at
            state.last_error = None
        return self.get(account_id)

    def mark_verified(self, account_id: str, verified_at: str) -> Account:
        with self._sessions.begin() as session:
            row = self._row(session, account_id)
            state = self._state(session, account_id)
            if row.status != AccountStatus.DISABLED.value:
                row.status = AccountStatus.CONNECTED.value
            row.last_verified_at = verified_at
            state.last_error = None
        return self.get(account_id)

    def mark_needs_reauth(self, account_id: str, reason: str) -> Account:
        with self._sessions.begin() as session:
            row = self._row(session, account_id)
            state = self._state(session, account_id)
            row.status = AccountStatus.NEEDS_REAUTH.value
            state.last_error = reason
        return self.get(account_id)

    def mark_unverified(self, account_id: str, reason: str) -> Account:
        with self._sessions.begin() as session:
            row = self._row(session, account_id)
            state = self._state(session, account_id)
            row.status = AccountStatus.UNVERIFIED.value
            state.last_error = reason
        return self.get(account_id)

    def set_watcher_enabled(self, account_id: str, enabled: bool) -> Account:
        with self._sessions.begin() as session:
            self._row(session, account_id)
            state = self._state(session, account_id)
            state.watcher_enabled = enabled
        return self.get(account_id)

    def update_policy_matching(self, old: SendPolicy, new: SendPolicy) -> int:
        with self._sessions.begin() as session:
            rows = session.scalars(
                select(AccountRow).where(
                    AccountRow.daily_allowance == old.daily_allowance,
                    AccountRow.window_start == old.window_start,
                    AccountRow.window_end == old.window_end,
                    AccountRow.jitter_min == old.jitter_min,
                    AccountRow.jitter_max == old.jitter_max,
                    AccountRow.max_in_flight == old.max_in_flight,
                    AccountRow.enabled == old.enabled,
                )
            ).all()
            for row in rows:
                row.daily_allowance = new.daily_allowance
                row.window_start = new.window_start
                row.window_end = new.window_end
                row.jitter_min = new.jitter_min
                row.jitter_max = new.jitter_max
                row.max_in_flight = new.max_in_flight
                row.enabled = new.enabled
            return len(rows)

    def reset_cursor(self, account_id: str, uidvalidity: int) -> None:
        with self._sessions.begin() as session:
            self._row(session, account_id)
            state = self._state(session, account_id)
            state.uidvalidity = uidvalidity
            state.last_uid = 0

    def set_baseline(
        self,
        account_id: str,
        uidvalidity: int,
        last_uid: int,
        synced_at: str,
    ) -> None:
        with self._sessions.begin() as session:
            self._row(session, account_id)
            state = self._state(session, account_id)
            if state.uidvalidity != uidvalidity:
                state.uidvalidity = uidvalidity
                state.last_uid = last_uid
            else:
                state.last_uid = max(state.last_uid, last_uid)
            state.last_sync_at = synced_at
            state.last_error = None
            state.consecutive_failures = 0

    def watcher_succeeded(self, account_id: str, synced_at: str) -> None:
        with self._sessions.begin() as session:
            state = session.get(AccountStateRow, account_id)
            if state is None:
                return
            state.last_sync_at = synced_at
            state.last_error = None
            state.consecutive_failures = 0

    def watcher_failed(self, account_id: str, reason: str) -> None:
        with self._sessions.begin() as session:
            state = session.get(AccountStateRow, account_id)
            if state is None:
                return
            state.last_error = reason
            state.consecutive_failures += 1

    def archive(self, account_id: str, archived_at: str) -> Account:
        with self._sessions.begin() as session:
            row = self._row(session, account_id)
            row.archived_at = archived_at
            state = self._state(session, account_id)
            state.watcher_enabled = False
        return self.get(account_id)

    def unarchive(self, account_id: str) -> Account:
        with self._sessions.begin() as session:
            row = self._row(session, account_id)
            row.archived_at = None
        return self.get(account_id)

    def deletion_counts(self, account_id: str) -> dict[str, int]:
        with self._sessions() as session:
            self._row(session, account_id)
            jobs = self._counts(session, JobRow.state, JobRow.account_id, account_id)
            batches = session.scalar(
                select(func.count(func.distinct(JobRow.batch_id))).where(
                    JobRow.account_id == account_id
                )
            )
            return {
                "jobs": sum(jobs.values()),
                "queued": jobs.get("queued", 0),
                "awaiting_approval": jobs.get("awaiting_approval", 0),
                "retry_wait": jobs.get("retry_wait", 0),
                "sending": jobs.get("sending", 0),
                "sent": jobs.get("sent", 0) + jobs.get("sent_unconfirmed", 0),
                "failed": jobs.get("failed", 0),
                "cancelled": jobs.get("cancelled", 0),
                "batches": int(batches or 0),
                "messages": self._count(session, MessageRow, account_id),
                "attempts": self._count(session, AttemptRow, account_id),
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
        session.delete(row)
        return AccountDelete(row.id, moved, 0, (), batches)

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

    def _row(self, session: Session, account_id: str) -> AccountRow:
        row = session.get(AccountRow, account_id)
        if row is None:
            raise AccountNotFound(f"no account {account_id}")
        return row

    def _state(self, session: Session, account_id: str) -> AccountStateRow:
        state = session.get(AccountStateRow, account_id)
        if state is None:
            state = AccountStateRow(account_id=account_id)
            session.add(state)
        return state
