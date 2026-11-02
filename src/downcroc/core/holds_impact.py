from __future__ import annotations

from downcroc.core.capacity import CapacityService
from downcroc.core.transports import TransportService
from downcroc.domain.accounts import Account
from downcroc.domain.jobs import JobState, SenderPolicy
from downcroc.runtime.config.schema import Settings
from downcroc.store.repositories.jobs import JobRepo

ACTIVE = (JobState.QUEUED, JobState.RETRY_WAIT, JobState.AWAITING_APPROVAL)


def account_impact(
    account: Account,
    *,
    settings: Settings,
    jobs: JobRepo,
    transports: TransportService,
    capacity: CapacityService,
) -> dict[str, object]:
    fleet = capacity.fleet()
    active = [
        job
        for job in jobs.list(account_id=account.id, limit=10_000)
        if job.state in ACTIVE
    ]
    pinned = sum(1 for job in active if job.sender_policy is SenderPolicy.PINNED)
    auto = sum(1 for job in active if job.sender_policy is SenderPolicy.AUTO)
    bindings = [
        {"id": item.id, "kind": item.kind.value}
        for item in transports.bindings(account)
    ]
    lost = (
        sum(1 if item["kind"] == "smtp" else 2 for item in bindings)
        if account.paused_at is not None
        else 0
    )
    lanes = fleet.api_lanes + (1 if fleet.smtp_seats else 0)
    advice = None
    if account.paused_at is not None and settings.dispatch.seat_hole_warn:
        if pinned:
            advice = (
                f"{account.address} is paused; {pinned} pinned jobs are held; "
                "reassign them or resume the account"
            )
        elif lost:
            advice = (
                f"{account.address} is paused; {lost} lane(s) are idle; "
                "resume the account or add a binding"
            )
    return {
        "lanes_before": lanes + lost,
        "lanes_after": lanes,
        "lost_lanes": lost,
        "auto_jobs": auto,
        "held_pinned": pinned,
        "absorbed_by": [],
        "idle_seats": [item["id"] for item in bindings],
        "advice": advice,
    }
