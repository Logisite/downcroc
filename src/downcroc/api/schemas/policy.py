from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from downcroc.domain.policy import POLICY_FIELDS, PolicyOverride, PolicyView
from downcroc.domain.validators import validate_policy

MAX_OVERRIDE_S = 2_592_000


class PolicyOverrideIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    daily_allowance: int | None = Field(default=None, ge=1, le=100_000)
    window_start: int | None = Field(default=None, ge=0, le=23)
    window_end: int | None = Field(default=None, ge=0, le=24)
    jitter_min: int | None = Field(default=None, ge=0, le=3_600)
    jitter_max: int | None = Field(default=None, ge=0, le=3_600)
    max_in_flight: int | None = Field(default=None, ge=1, le=64)
    enabled: bool | None = None
    for_s: int | None = Field(default=None, ge=1, le=MAX_OVERRIDE_S)
    reason: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def coherent(self) -> PolicyOverrideIn:
        values = self.override().values()
        validate_policy(values)
        return self

    def override(self) -> PolicyOverride:
        return PolicyOverride(
            daily_allowance=self.daily_allowance,
            window_start=self.window_start,
            window_end=self.window_end,
            jitter_min=self.jitter_min,
            jitter_max=self.jitter_max,
            max_in_flight=self.max_in_flight,
            enabled=self.enabled,
        )


class PolicyOut(BaseModel):
    scope: str
    values: dict[str, Any]
    sources: dict[str, str]
    expires_at: str | None
    permanent: dict[str, Any] | None
    temporary: dict[str, Any] | None

    @classmethod
    def build(cls, view: PolicyView) -> PolicyOut:
        return cls(
            scope=view.scope,
            values=view.values.__dict__,
            sources=view.sources,
            expires_at=view.expires_at,
            permanent=_document(view.permanent),
            temporary=_document(view.temporary),
        )


def _document(override: PolicyOverride | None) -> dict[str, Any] | None:
    if override is None:
        return None
    return {
        field: getattr(override, field)
        for field in POLICY_FIELDS
        if getattr(override, field) is not None
    }
