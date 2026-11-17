from __future__ import annotations

from dataclasses import dataclass

from downcroc.core.outbound.backfill.plan import blocked_reason
from downcroc.domain.accounts import Account
from downcroc.domain.errors import (
    AccountNotFound,
    BackfillHoleNotFound,
    BackfillHoleResolved,
)
from downcroc.domain.providers import ProviderSpec
from downcroc.providers.registry import ProviderRegistry
from downcroc.runtime.clock import utc_now
from downcroc.store.repositories.accounts import AccountRepo
from downcroc.store.repositories.thread_backfill import (
    HoleCounts,
    HoleDetail,
    ThreadBackfillRepo,
)


@dataclass(frozen=True)
class AccountBackfill:
    """One account's backfill state, including why it cannot make progress."""

    account_id: str
    address: str | None
    status: str
    due: int
    waiting: int
    missing: int
    unresolved: int
    next_due_at: str | None
    blocked_reason: str | None

    @property
    def open(self) -> int:
        return self.due + self.waiting

    @property
    def total(self) -> int:
        return self.open + self.missing + self.unresolved


@dataclass(frozen=True)
class BackfillStatus:
    checked_at: str
    due: int
    waiting: int
    missing: int
    unresolved: int
    next_due_at: str | None
    accounts: tuple[AccountBackfill, ...]
    unknown_accounts: tuple[str, ...]

    @property
    def open(self) -> int:
        return self.due + self.waiting

    @property
    def total(self) -> int:
        return self.open + self.missing + self.unresolved


@dataclass(frozen=True)
class HoleExplanation:
    """One hole plus the account state that decides whether it can move."""

    detail: HoleDetail
    address: str | None
    account_status: str | None
    blocked_reason: str | None


class BackfillService:
    """Read and diagnose the thread-id backfill without touching the worker."""

    def __init__(
        self,
        holes: ThreadBackfillRepo,
        accounts: AccountRepo,
        providers: ProviderRegistry,
    ) -> None:
        self._holes = holes
        self._accounts = accounts
        self._providers = providers

    def status(self) -> BackfillStatus:
        counts = self._holes.counts()
        known = {account.id: account for account in self._accounts.list()}
        rows: list[AccountBackfill] = []
        unknown: list[str] = []
        for account_id in sorted(counts):
            row = counts[account_id]
            account = known.get(account_id)
            if account is None:
                unknown.append(account_id)
            rows.append(self._row(row, account))
        return BackfillStatus(
            checked_at=utc_now(),
            due=sum(row.due for row in rows),
            waiting=sum(row.waiting for row in rows),
            missing=sum(row.missing for row in rows),
            unresolved=sum(row.unresolved for row in rows),
            next_due_at=_first_stamp(row.next_due_at for row in rows),
            accounts=tuple(rows),
            unknown_accounts=tuple(unknown),
        )

    def explain(self, attempt_id: str) -> HoleExplanation:
        detail = self._holes.detail(attempt_id)
        if detail is None:
            raise BackfillHoleNotFound(
                "that send has no recorded thread id hole",
                fields={"attempt": attempt_id},
            )
        account = self._account(detail.account_id)
        return HoleExplanation(
            detail=detail,
            address=account.address if account is not None else None,
            account_status=account.status.value if account is not None else None,
            blocked_reason=self._reason(account),
        )

    def retry(self, attempt_id: str) -> HoleExplanation:
        detail = self._holes.detail(attempt_id)
        if detail is None:
            raise BackfillHoleNotFound(
                "that send has no recorded thread id hole",
                fields={"attempt": attempt_id},
            )
        if not self._holes.reopen(attempt_id):
            raise BackfillHoleResolved(
                "that hole already has a thread id",
                fields={"attempt": attempt_id},
                hint="run `downcroc backfill explain` to see the stored thread",
            )
        return self.explain(attempt_id)

    def _row(self, row: HoleCounts, account: Account | None) -> AccountBackfill:
        return AccountBackfill(
            account_id=row.account_id,
            address=account.address if account is not None else None,
            status=account.status.value if account is not None else "unknown",
            due=row.due,
            waiting=row.waiting,
            missing=row.missing,
            unresolved=row.unresolved,
            next_due_at=row.next_due_at,
            blocked_reason=self._reason(account),
        )

    def _account(self, account_id: str | None) -> Account | None:
        if account_id is None:
            return None
        try:
            return self._accounts.get(account_id)
        except AccountNotFound:
            return None

    def _reason(self, account: Account | None) -> str | None:
        return blocked_reason(account, self._spec)

    def _spec(self, account: Account) -> ProviderSpec | None:
        try:
            return self._providers.get(account.provider)
        except KeyError:
            return None


def _first_stamp(values) -> str | None:
    stamps = [value for value in values if value is not None]
    return min(stamps) if stamps else None
