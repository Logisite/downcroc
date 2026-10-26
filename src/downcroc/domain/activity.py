from __future__ import annotations

from dataclasses import dataclass

ACTIVITY_FIELDS = (
    "sent",
    "failed",
    "received",
    "replies",
    "bounces",
    "suppressed",
)


@dataclass(frozen=True)
class ActivityTotals:
    sent: int = 0
    failed: int = 0
    received: int = 0
    replies: int = 0
    bounces: int = 0
    suppressed: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "sent": self.sent,
            "failed": self.failed,
            "received": self.received,
            "replies": self.replies,
            "bounces": self.bounces,
            "suppressed": self.suppressed,
        }


@dataclass(frozen=True)
class AccountActivity:
    account_id: str
    totals: ActivityTotals


@dataclass(frozen=True)
class HourlyActivity:
    account_id: str
    hour_start: str
    totals: ActivityTotals


@dataclass(frozen=True)
class DailyActivity:
    account_id: str
    day: str
    totals: ActivityTotals
    quota_limit: int


@dataclass(frozen=True)
class BatchCounters:
    batch_id: str
    queued: int
    sent: int
    failed: int
    suppressed: int
    invalid: int
    inbound: int
    replies: int
    late_replies: int
    bounces: int
    updated_at: str


@dataclass(frozen=True)
class ActivitySummary:
    accounts: tuple[AccountActivity, ...]
    total: ActivityTotals


@dataclass(frozen=True)
class AccountStats:
    account_id: str
    address: str
    totals: ActivityTotals
    remaining_allowance: int


@dataclass(frozen=True)
class BatchStats:
    batch_id: str
    kind: str
    name: str
    counters: BatchCounters
    reply_rate: float
