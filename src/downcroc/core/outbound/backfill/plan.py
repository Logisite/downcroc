from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from downcroc.domain.accounts import Account, AccountStatus
from downcroc.domain.providers import ProviderSpec
from downcroc.store.repositories.thread_backfill import HoleCounts


@dataclass(frozen=True)
class AccountPlan:
    account: Account
    spec: ProviderSpec
    counts: HoleCounts


@dataclass(frozen=True)
class BlockedAccount:
    account_id: str
    reason: str
    holes: int


@dataclass(frozen=True)
class PassPlan:
    """The work one pass can actually attempt, split by why it cannot."""

    accounts: tuple[AccountPlan, ...]
    blocked_accounts: tuple[BlockedAccount, ...]
    due: int
    waiting: int
    blocked: int
    missing: int
    unresolved: int
    next_due_at: str | None
    holes: int

    @property
    def left(self) -> int:
        return self.due + self.waiting + self.blocked


def build_plan(
    counts: dict[str, HoleCounts],
    known: dict[str, Account],
    spec_for: Callable[[Account], ProviderSpec | None],
    *,
    now: str,
) -> PassPlan:
    accounts: list[AccountPlan] = []
    blocked: list[BlockedAccount] = []
    due = 0
    waiting = 0
    blocked_holes = 0
    missing = 0
    unresolved = 0
    holes = 0
    next_due: str | None = None
    for account_id in sorted(counts):
        row = counts[account_id]
        holes += row.total
        missing += row.missing
        unresolved += row.unresolved
        account = known.get(account_id)
        reason = blocked_reason(account, spec_for)
        if reason is not None or account is None:
            blocked_holes += row.open
            blocked.append(
                BlockedAccount(
                    account_id=account_id,
                    reason=reason or "unknown_account",
                    holes=row.open,
                )
            )
            continue
        spec = spec_for(account)
        if spec is None:
            blocked_holes += row.open
            blocked.append(
                BlockedAccount(
                    account_id=account_id, reason="provider_missing", holes=row.open
                )
            )
            continue
        due += row.due
        waiting += row.waiting
        if row.due:
            next_due = now
        elif row.next_due_at is not None and (
            next_due is None or row.next_due_at < next_due
        ):
            next_due = row.next_due_at
        accounts.append(AccountPlan(account=account, spec=spec, counts=row))
    return PassPlan(
        accounts=tuple(accounts),
        blocked_accounts=tuple(blocked),
        due=due,
        waiting=waiting,
        blocked=blocked_holes,
        missing=missing,
        unresolved=unresolved,
        next_due_at=next_due,
        holes=holes,
    )


def blocked_reason(
    account: Account | None,
    spec_for: Callable[[Account], ProviderSpec | None],
) -> str | None:
    if account is None:
        return "unknown_account"
    if account.status is not AccountStatus.CONNECTED:
        return account.status.value
    spec = spec_for(account)
    if spec is None:
        return "provider_missing"
    if not spec.api_configured:
        return "api_not_configured"
    return None
