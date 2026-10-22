from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from downcroc.domain.accounts import Account
from downcroc.domain.attempts import ConnectAttempt
from downcroc.domain.providers import ProviderSpec


class AccountCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1, max_length=64)
    address: str = Field(min_length=3, max_length=320)
    label: str = Field(default="", max_length=80)


class AppPasswordConnect(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=1, max_length=1024)


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
    last_error: str | None
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
            last_error=account.last_error,
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


class AttemptOut(BaseModel):
    id: str
    account_id: str
    kind: str
    state: str
    authorization_url: str
    expires_at: str
    created_at: str
    error: str | None

    @classmethod
    def of(cls, attempt: ConnectAttempt) -> AttemptOut:
        return cls(
            id=attempt.id,
            account_id=attempt.account_id,
            kind=attempt.kind.value,
            state=attempt.state.value,
            authorization_url=attempt.authorization_url,
            expires_at=attempt.expires_at,
            created_at=attempt.created_at,
            error=attempt.error,
        )


class ProviderOut(BaseModel):
    id: str
    label: str
    auth_kind: str
    imap_host: str
    imap_port: int
    imap_tls: str
    smtp_host: str
    smtp_port: int
    smtp_tls: str
    smtp_auth_mechanism: str
    sent_folder: str
    supports_idle: bool
    requires_user_agent: bool
    attachment_max_bytes: int
    notes: str
    oauth_configured: bool

    @classmethod
    def of(cls, spec: ProviderSpec) -> ProviderOut:
        return cls(
            id=spec.id,
            label=spec.label,
            auth_kind=spec.auth_kind.value,
            imap_host=spec.imap_host,
            imap_port=spec.imap_port,
            imap_tls=spec.imap_tls.value,
            smtp_host=spec.smtp_host,
            smtp_port=spec.smtp_port,
            smtp_tls=spec.smtp_tls.value,
            smtp_auth_mechanism=spec.smtp_auth_mechanism,
            sent_folder=spec.sent_folder,
            supports_idle=spec.supports_idle,
            requires_user_agent=spec.requires_user_agent,
            attachment_max_bytes=spec.attachment_max_bytes,
            notes=spec.notes,
            oauth_configured=spec.oauth_configured,
        )
