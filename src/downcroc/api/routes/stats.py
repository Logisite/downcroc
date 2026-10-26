from __future__ import annotations

from fastapi import APIRouter, Query, Request

from downcroc.api.schemas.stats import (
    AccountRowOut,
    AccountsOut,
    BatchesOut,
    BatchRowOut,
    DailyOut,
    DailyRowOut,
    HourlyOut,
    HourlyRowOut,
    PruneOut,
    RebuildOut,
    RebuildRequest,
    SummaryOut,
)
from downcroc.core.bootstrap import Services

router = APIRouter(prefix="/api/stats", tags=["stats"])


def _services(request: Request) -> Services:
    return request.app.state.services


@router.get("/summary", response_model=SummaryOut)
def summary(
    request: Request,
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = None,
    account_id: str | None = None,
) -> SummaryOut:
    chosen, found = _services(request).stats.summary(from_, to, account_id)
    return SummaryOut.of(chosen.start_day, chosen.end_day, found)


@router.get("/hourly", response_model=HourlyOut)
def hourly(
    request: Request,
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = None,
    account_id: str | None = None,
) -> HourlyOut:
    chosen, points = _services(request).stats.hourly(from_, to, account_id)
    return HourlyOut(
        from_=chosen.start_day,
        to=chosen.end_day,
        rows=[HourlyRowOut.of(point) for point in points],
    )


@router.get("/daily", response_model=DailyOut)
def daily(
    request: Request,
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = None,
    account_id: str | None = None,
) -> DailyOut:
    chosen, points = _services(request).stats.daily(from_, to, account_id)
    return DailyOut(
        from_=chosen.start_day,
        to=chosen.end_day,
        rows=[DailyRowOut.of(point) for point in points],
    )


@router.get("/batches", response_model=BatchesOut)
def batches(
    request: Request,
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = None,
) -> BatchesOut:
    chosen, rows = _services(request).stats.batches_for(from_, to)
    return BatchesOut(
        from_=chosen.start_day,
        to=chosen.end_day,
        rows=[BatchRowOut.of(item) for item in rows],
    )


@router.get("/accounts", response_model=AccountsOut)
def accounts(
    request: Request,
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = None,
    account_id: str | None = None,
) -> AccountsOut:
    chosen, rows = _services(request).stats.accounts_for(from_, to, account_id)
    return AccountsOut(
        from_=chosen.start_day,
        to=chosen.end_day,
        rows=[AccountRowOut.of(item) for item in rows],
    )


@router.post("/rebuild", response_model=RebuildOut)
def rebuild(request: Request, body: RebuildRequest | None = None) -> RebuildOut:
    result = _services(request).stats.rebuild(None if body is None else body.since)
    return RebuildOut(
        since=result.since,
        rows=result.rows,
        duration_ms=result.duration_ms,
    )


@router.post("/prune", response_model=PruneOut)
def prune(request: Request) -> PruneOut:
    result = _services(request).retention.prune()
    return PruneOut(tables=result.tables, bytes=result.bytes)
