from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from downcroc.domain.accounts import Account


class AccountCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1, max_length=64)
    address: str = Field(min_length=3, max_length=320)
    label: str = Field(default="", max_length=80)


class QuotaOut(BaseModel):
    daily_allowance: int
    window_start: int
    window_end: int
    jitter_min: int
    jitter_max: int
    max_in_flight: int
    enabled: bool


class AccountOut(BaseModel):
    id: str
    provider: str
    address: str
    label: str
    status: str
    credential_present: bool
    created_at: str
    last_verified_at: str | None
    quota: QuotaOut

    @classmethod
    def of(cls, account: Account) -> AccountOut:
        return cls(
            id=account.id,
            provider=account.provider,
            address=account.address,
            label=account.label,
            status=account.status.value,
            credential_present=account.credential_present,
            created_at=account.created_at,
            last_verified_at=account.last_verified_at,
            quota=QuotaOut(
                daily_allowance=account.policy.daily_allowance,
                window_start=account.policy.window_start,
                window_end=account.policy.window_end,
                jitter_min=account.policy.jitter_min,
                jitter_max=account.policy.jitter_max,
                max_in_flight=account.policy.max_in_flight,
                enabled=account.policy.enabled,
            ),
        )
