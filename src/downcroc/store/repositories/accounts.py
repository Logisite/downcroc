from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from downcroc.domain.accounts import Account, AccountStatus, SendPolicy
from downcroc.domain.errors import AccountExists, AccountInUse, AccountNotFound
from downcroc.store.db.models import AccountRow, AccountStateRow, JobRow


def _to_account(row: AccountRow) -> Account:
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
    )


class AccountRepo:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def list(self) -> list[Account]:
        with self._sessions() as session:
            rows = session.scalars(
                select(AccountRow).order_by(AccountRow.created_at, AccountRow.id)
            ).all()
            return [_to_account(row) for row in rows]

    def get(self, account_id: str) -> Account:
        with self._sessions() as session:
            row = session.get(AccountRow, account_id)
            if row is None:
                raise AccountNotFound(f"no account {account_id}")
            return _to_account(row)

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
