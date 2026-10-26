from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from downcroc.domain.activity import (
    AccountStats,
    ActivitySummary,
    ActivityTotals,
    BatchStats,
    DailyActivity,
    HourlyActivity,
)


class TotalsOut(BaseModel):
    sent: int
    failed: int
    received: int
    replies: int
    bounces: int
    suppressed: int

    @classmethod
    def of(cls, totals: ActivityTotals) -> TotalsOut:
        return cls(**totals.as_dict())


class AccountSummaryOut(TotalsOut):
    account_id: str


class SummaryOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from")
    to: str
    accounts: list[AccountSummaryOut]
    total: TotalsOut

    @classmethod
    def of(
        cls,
        from_value: str,
        to_value: str,
        summary: ActivitySummary,
    ) -> SummaryOut:
        return cls(
            from_=from_value,
            to=to_value,
            accounts=[
                AccountSummaryOut(
                    account_id=item.account_id,
                    **item.totals.as_dict(),
                )
                for item in summary.accounts
            ],
            total=TotalsOut.of(summary.total),
        )


class HourlyRowOut(TotalsOut):
    account_id: str
    hour_start: str

    @classmethod
    def of(cls, point: HourlyActivity) -> HourlyRowOut:
        return cls(
            account_id=point.account_id,
            hour_start=point.hour_start,
            **point.totals.as_dict(),
        )


class HourlyOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from")
    to: str
    rows: list[HourlyRowOut]


class DailyRowOut(TotalsOut):
    account_id: str
    day: str
    quota_limit: int

    @classmethod
    def of(cls, point: DailyActivity) -> DailyRowOut:
        return cls(
            account_id=point.account_id,
            day=point.day,
            quota_limit=point.quota_limit,
            **point.totals.as_dict(),
        )


class DailyOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from")
    to: str
    rows: list[DailyRowOut]


class BatchRowOut(TotalsOut):
    batch_id: str
    kind: str
    name: str
    queued: int
    invalid: int
    late_replies: int
    reply_rate: float

    @classmethod
    def of(cls, item: BatchStats) -> BatchRowOut:
        counters = item.counters
        return cls(
            batch_id=item.batch_id,
            kind=item.kind,
            name=item.name,
            queued=counters.queued,
            invalid=counters.invalid,
            late_replies=counters.late_replies,
            reply_rate=item.reply_rate,
            sent=counters.sent,
            failed=counters.failed,
            received=counters.inbound,
            replies=counters.replies,
            bounces=counters.bounces,
            suppressed=counters.suppressed,
        )


class BatchesOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from")
    to: str
    rows: list[BatchRowOut]


class AccountRowOut(TotalsOut):
    account_id: str
    address: str
    remaining_allowance: int

    @classmethod
    def of(cls, item: AccountStats) -> AccountRowOut:
        return cls(
            account_id=item.account_id,
            address=item.address,
            remaining_allowance=item.remaining_allowance,
            **item.totals.as_dict(),
        )


class AccountsOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from")
    to: str
    rows: list[AccountRowOut]


class RebuildRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    since: str | None = None


class RebuildOut(BaseModel):
    since: str | None
    rows: int
    duration_ms: int


class PruneOut(BaseModel):
    tables: dict[str, int]
    bytes: int
