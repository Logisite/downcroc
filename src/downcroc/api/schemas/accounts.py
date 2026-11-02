from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from downcroc.domain.accounts import Account
from downcroc.domain.attempts import ConnectAttempt
from downcroc.domain.policy import SendPolicy
from downcroc.domain.providers import ProviderSpec
from downcroc.domain.transports import AccountTransport
from downcroc.providers.registry import readiness


class AccountCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1, max_length=64)
    address: str = Field(min_length=3, max_length=320)
    label: str = Field(default="", max_length=80)


class AppPasswordConnect(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=1, max_length=1024)


class WatcherToggle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool


class SyncOut(BaseModel):
    last_uid: int
    uidvalidity: int
    last_sync_at: str | None
    last_error: str | None
    consecutive_failures: int
    cursor_source: str | None = None
    history_id: str | None = None
    last_sweep_at: str | None = None
    last_source_switch_at: str | None = None


class InboundOut(BaseModel):
    owner: str
    mode: str
    override: str | None = None
    cursor_source: str | None = None
    history_id: str | None = None
    last_sweep_at: str | None = None
    last_source_switch_at: str | None = None


class InboundUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["auto", "imap", "gmail_api"]


class QuotaOut(BaseModel):
    daily_allowance: int
    window_start: int
    window_end: int
    jitter_min: int
    jitter_max: int
    max_in_flight: int
    enabled: bool
    used: int = 0
    reserved: int = 0
    available: int = 0


class AccountOut(BaseModel):
    id: str
    provider: str
    address: str
    label: str
    status: str
    credential_present: bool
    created_at: str
    last_verified_at: str | None
    archived_at: str | None
    last_error: str | None
    watcher_enabled: bool
    paused_at: str | None = None
    paused_reason: str | None = None
    sync: SyncOut
    inbound: InboundOut
    quota: QuotaOut

    @classmethod
    def of(
        cls,
        account: Account,
        policy: SendPolicy,
        *,
        mode: str | None = None,
        used: int = 0,
        reserved: int = 0,
        available: int = 0,
    ) -> AccountOut:
        owner = account.inbound_source or "imap"
        return cls(
            id=account.id,
            provider=account.provider,
            address=account.address,
            label=account.label,
            status=account.status.value,
            credential_present=account.credential_present,
            created_at=account.created_at,
            last_verified_at=account.last_verified_at,
            archived_at=account.archived_at,
            last_error=account.last_error,
            watcher_enabled=account.watcher_enabled,
            paused_at=account.paused_at,
            paused_reason=account.paused_reason,
            sync=SyncOut(
                last_uid=account.last_uid,
                uidvalidity=account.uidvalidity,
                last_sync_at=account.last_sync_at,
                last_error=account.last_error,
                consecutive_failures=account.consecutive_failures,
                cursor_source=account.cursor_source,
                history_id=account.history_id,
                last_sweep_at=account.last_sweep_at,
                last_source_switch_at=account.last_source_switch_at,
            ),
            inbound=InboundOut(
                owner=owner,
                mode=mode or ("api_poll" if owner == "gmail_api" else "imap_poll"),
                override=account.source_override,
                cursor_source=account.cursor_source,
                history_id=account.history_id,
                last_sweep_at=account.last_sweep_at,
                last_source_switch_at=account.last_source_switch_at,
            ),
            quota=QuotaOut(
                daily_allowance=policy.daily_allowance,
                window_start=policy.window_start,
                window_end=policy.window_end,
                jitter_min=policy.jitter_min,
                jitter_max=policy.jitter_max,
                max_in_flight=policy.max_in_flight,
                enabled=policy.enabled,
                used=used,
                reserved=reserved,
                available=available,
            ),
        )


class AccountDeletionCounts(BaseModel):
    jobs: int = 0
    pinned_jobs: int = 0
    auto_jobs: int = 0
    queued: int = 0
    awaiting_approval: int = 0
    retry_wait: int = 0
    sending: int = 0
    sent: int = 0
    failed: int = 0
    cancelled: int = 0
    batches: int = 0
    batches_pinned: int = 0
    messages: int = 0
    attempts: int = 0
    activity: int = 0
    quota: int = 0


class AccountDeletionOut(BaseModel):
    account_id: str
    counts: AccountDeletionCounts
    blockers: list[str]


class AccountDeleteOut(BaseModel):
    account_id: str
    reassigned: int
    deleted_jobs: int


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


class TransportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = Field(min_length=1, max_length=16)
    priority: int = 0
    max_concurrency: int = Field(default=1, ge=1)
    rate_per_min: int | None = Field(default=None, ge=1)
    oauth_client_id: str | None = None


class TransportUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    priority: int | None = None
    max_concurrency: int | None = Field(default=None, ge=1)
    rate_per_min: int | None = Field(default=None, ge=1)
    enabled: bool | None = None


class TransportOut(BaseModel):
    id: str
    account_id: str
    provider_id: str
    kind: str
    oauth_client_id: str | None
    enabled: bool
    priority: int
    max_concurrency: int
    rate_per_min: int | None
    health: str
    cooldown_until: str | None
    last_error_code: str | None
    last_error_message: str | None
    last_success_at: str | None
    created_at: str
    updated_at: str
    slot: str | None = None

    @classmethod
    def of(cls, binding: AccountTransport, slot: str | None = None) -> TransportOut:
        return cls(
            id=binding.id,
            account_id=binding.account_id,
            provider_id=binding.provider_id,
            kind=binding.kind.value,
            oauth_client_id=binding.oauth_client_id,
            enabled=binding.enabled,
            priority=binding.priority,
            max_concurrency=binding.max_concurrency,
            rate_per_min=binding.rate_per_min,
            health=binding.health.value,
            cooldown_until=binding.cooldown_until,
            last_error_code=binding.last_error_code,
            last_error_message=binding.last_error_message,
            last_success_at=binding.last_success_at,
            created_at=binding.created_at,
            updated_at=binding.updated_at,
            slot=slot,
        )


class TransportTestOut(BaseModel):
    ok: bool
    code: str | None
    message: str
    health: str


class TransportEventOut(BaseModel):
    seq: int
    type: str
    ts: str
    reason: object | None = None
    retry_s: object | None = None


class ProviderIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str | None = None
    imap_host: str | None = None
    imap_port: int | None = Field(default=None, ge=1, le=65535)
    imap_tls: str | None = None
    smtp_host: str | None = None
    smtp_port: int | None = Field(default=None, ge=1, le=65535)
    smtp_tls: str | None = None
    auth_kind: str | None = None
    smtp_auth_mechanism: str | None = None
    sent_folder: str | None = None
    notes: str | None = None
    oauth_client_id: str | None = None
    oauth_client_secret: str | None = None
    oauth_tenant: str | None = None
    transport: str | None = None
    api_base_url: str | None = None
    api_max_concurrency: int | None = Field(default=None, ge=1)
    api_rate_per_min: int | None = Field(default=None, ge=1)
    api_scopes: list[str] | None = None


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
    sent_folder: str
    supports_idle: bool
    requires_user_agent: bool
    attachment_max_bytes: int
    notes: str
    oauth_configured: bool
    transport: str
    api_base_url: str
    api_max_concurrency: int
    api_rate_per_min: int
    api_scopes: list[str]
    ready: bool = False
    missing: list[str] = Field(default_factory=list)
    source: str | None = None

    @classmethod
    def of(cls, spec: ProviderSpec, *, source: str | None = None) -> ProviderOut:
        ready, missing = readiness(spec)
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
            sent_folder=spec.sent_folder,
            supports_idle=spec.supports_idle,
            requires_user_agent=spec.requires_user_agent,
            attachment_max_bytes=spec.attachment_max_bytes,
            notes=spec.notes,
            oauth_configured=spec.oauth_configured,
            transport=spec.transport,
            api_base_url=spec.api_base_url,
            api_max_concurrency=spec.api_max_concurrency,
            api_rate_per_min=spec.api_rate_per_min,
            api_scopes=list(spec.api_scopes),
            ready=ready,
            missing=missing,
            source=source,
        )
