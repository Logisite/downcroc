from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from downcroc.domain.accounts import Account, AccountStatus, SendPolicy
from downcroc.domain.errors import AccountExists, AccountInUse, AccountNotFound
from downcroc.store.db.models import AccountRow, AccountStateRow, JobRow


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

    def list(self) -> list[Account]:
        with self._sessions() as session:
            rows = session.execute(
                select(AccountRow, AccountStateRow)
                .outerjoin(AccountStateRow, AccountStateRow.account_id == AccountRow.id)
                .order_by(AccountRow.created_at, AccountRow.id)
            ).all()
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

    def delete(self, account_id: str) -> None:
        with self._sessions.begin() as session:
            row = session.get(AccountRow, account_id)
            if row is None:
                raise AccountNotFound(f"no account {account_id}")
            jobs = session.scalar(
                select(func.count())
                .select_from(JobRow)
                .where(JobRow.account_id == account_id)
            )
            if jobs:
                raise AccountInUse(
                    f"account {account_id} has {jobs} jobs",
                    hint="delete the jobs before removing the account",
                )
            session.delete(row)

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
