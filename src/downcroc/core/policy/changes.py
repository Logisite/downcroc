from __future__ import annotations

from downcroc.core.events import EventBus
from downcroc.domain.policy import POLICY_FIELDS, PolicyOverride, SendPolicy
from downcroc.runtime.logging.setup import EventLogger


def values(policy: SendPolicy | PolicyOverride) -> dict[str, object]:
    return {field: getattr(policy, field) for field in POLICY_FIELDS}


def resolved(
    log: EventLogger,
    bus: EventBus,
    *,
    scope: str,
    previous: SendPolicy,
    current: SendPolicy,
    source: str | None,
) -> None:
    if previous.daily_allowance == current.daily_allowance:
        return
    fields = {
        "account": scope,
        "limit": current.daily_allowance,
        "source": source,
        "previous": previous.daily_allowance,
    }
    log.info("policy.resolved", **fields)
    bus.publish("policy.resolved", fields)
