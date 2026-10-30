from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace

POLICY_FIELDS = (
    "daily_allowance",
    "window_start",
    "window_end",
    "jitter_min",
    "jitter_max",
    "max_in_flight",
    "enabled",
)


@dataclass(frozen=True)
class SendPolicy:
    daily_allowance: int
    window_start: int
    window_end: int
    jitter_min: int
    jitter_max: int
    max_in_flight: int
    enabled: bool


@dataclass(frozen=True)
class PolicyOverride:
    daily_allowance: int | None = None
    window_start: int | None = None
    window_end: int | None = None
    jitter_min: int | None = None
    jitter_max: int | None = None
    max_in_flight: int | None = None
    enabled: bool | None = None
    expires_at: str | None = None

    def values(self) -> dict[str, object]:
        return {
            field: getattr(self, field)
            for field in POLICY_FIELDS
            if getattr(self, field) is not None
        }

    def empty(self) -> bool:
        return not self.values()

    def apply(self, policy: SendPolicy) -> SendPolicy:
        return replace(policy, **self.values())

    @classmethod
    def from_mapping(cls, values: Mapping[str, object]) -> PolicyOverride:
        known = {
            field: values[field]
            for field in POLICY_FIELDS
            if values.get(field) is not None
        }
        return cls(**known)


@dataclass(frozen=True)
class ResolvedPolicy:
    values: SendPolicy
    sources: dict[str, str]
    expires_at: str | None = None

    def source(self, field: str) -> str:
        return self.sources.get(field, "default")


@dataclass(frozen=True)
class PolicyView:
    scope: str
    values: SendPolicy
    sources: dict[str, str]
    expires_at: str | None
    permanent: PolicyOverride | None
    temporary: PolicyOverride | None


def tighten(policy: SendPolicy, limits: PolicyOverride) -> SendPolicy:
    """Apply batch limits that may only slow the mailbox down."""
    changes: dict[str, object] = {}
    if limits.daily_allowance is not None:
        changes["daily_allowance"] = min(policy.daily_allowance, limits.daily_allowance)
    if limits.max_in_flight is not None:
        changes["max_in_flight"] = min(policy.max_in_flight, limits.max_in_flight)
    if limits.jitter_min is not None:
        changes["jitter_min"] = max(policy.jitter_min, limits.jitter_min)
    if limits.jitter_max is not None:
        changes["jitter_max"] = max(policy.jitter_max, limits.jitter_max)
    if not changes:
        return policy
    tightened = replace(policy, **changes)
    if tightened.jitter_max < tightened.jitter_min:
        tightened = replace(tightened, jitter_max=tightened.jitter_min)
    return tightened
