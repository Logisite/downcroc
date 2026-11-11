from __future__ import annotations

from downcroc.domain.accounts import Account, AccountStatus
from downcroc.domain.errors import (
    AccountArchived,
    AccountNeedsReauth,
    AccountPending,
    AccountUnavailable,
)
from downcroc.store.repositories.batches import BatchRepo

MANUAL_BATCH = "manual"


def is_manual_batch(batch_id: str) -> bool:
    return batch_id == MANUAL_BATCH


def require_batch(batches: BatchRepo, batch_id: str) -> None:
    if not is_manual_batch(batch_id):
        batches.get(batch_id)


def is_usable(account: Account) -> bool:
    return (
        account.archived_at is None
        and account.status is AccountStatus.CONNECTED
        and account.paused_at is None
    )


def require_usable(account: Account) -> None:
    if account.archived_at is not None:
        raise AccountArchived(
            f"account {account.id} is archived",
            hint="unarchive the account before creating or sending a job",
        )
    if account.status is AccountStatus.PENDING:
        raise AccountPending(
            f"account {account.id} is pending",
            hint="connect the account before creating or sending a job",
        )
    if account.status is AccountStatus.NEEDS_REAUTH:
        raise AccountNeedsReauth(
            f"account {account.id} needs to be reconnected",
            hint="start a new connect attempt",
        )
    if account.status is not AccountStatus.CONNECTED:
        raise AccountUnavailable(
            f"account {account.id} is {account.status.value}",
            hint="connect the account before creating or sending a job",
        )
    if account.paused_at is not None:
        raise AccountUnavailable(
            f"account {account.id} is paused",
            hint="resume the account before creating or sending a job",
        )
