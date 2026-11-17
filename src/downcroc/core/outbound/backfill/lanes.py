from __future__ import annotations

from dataclasses import dataclass, field

from downcroc.domain.accounts import Account
from downcroc.domain.providers import ProviderSpec
from downcroc.store.repositories.thread_backfill import HoleCounts


@dataclass
class PassStats:
    """Outcome counters for one drain turn, one account, or a whole pass."""

    resolved: int = 0
    missing: int = 0
    waiting: int = 0
    unresolved: int = 0
    errors: int = 0

    @property
    def progress(self) -> int:
        return self.resolved + self.missing + self.waiting + self.unresolved

    def add(self, other: PassStats) -> None:
        self.resolved += other.resolved
        self.missing += other.missing
        self.waiting += other.waiting
        self.unresolved += other.unresolved
        self.errors += other.errors


@dataclass
class Lane:
    """One account's drain turn inside a pass."""

    account: Account
    spec: ProviderSpec
    counts: HoleCounts
    stats: PassStats = field(default_factory=PassStats)
    swept: bool = False
    sweep_threads: dict[str, set[str]] | None = None
