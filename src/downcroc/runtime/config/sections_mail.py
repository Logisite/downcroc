from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from downcroc.runtime.config.schema_common import RESTART


class EventsSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ring_size: int = Field(
        default=10_000,
        ge=1,
        le=1_000_000,
        description="Number of recent events kept for replay.",
        json_schema_extra=RESTART,
    )
    queue_size: int = Field(
        default=1000,
        ge=16,
        le=100_000,
        description="Maximum queued events per stream subscriber.",
        json_schema_extra=RESTART,
    )
    keepalive_s: float = Field(
        default=15.0,
        gt=0,
        le=300,
        description="Seconds between SSE keepalive frames.",
    )


class VaultSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kdf_memory_kib: int = Field(
        default=65_536,
        ge=8192,
        le=1_048_576,
        description="Argon2id memory in KiB when a vault is created.",
    )
    kdf_iterations: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Argon2id iterations when a vault is created.",
    )
    kdf_lanes: int = Field(
        default=1,
        ge=1,
        le=8,
        description="Argon2id lanes when a vault is created.",
    )
    kdf_target_ms: int = Field(
        default=250,
        ge=50,
        le=2000,
        description="Target derivation time in milliseconds.",
    )
    kdf_max_memory_kib: int = Field(
        default=262_144,
        ge=8192,
        le=1_048_576,
        description="Maximum Argon2id memory in KiB.",
    )
    free_attempts: int = Field(
        default=5,
        ge=0,
        le=100,
        description="Failed unlocks allowed before throttling starts.",
    )
    base_delay_s: float = Field(
        default=1.0,
        gt=0,
        le=60,
        description="Base throttle delay in seconds after failed unlocks.",
    )
    max_delay_s: float = Field(
        default=300.0,
        ge=1,
        le=3600,
        description="Maximum throttle delay in seconds.",
    )

    @model_validator(mode="after")
    def ordered_vault(self) -> VaultSettings:
        if self.kdf_max_memory_kib < self.kdf_memory_kib:
            raise ValueError("kdf_max_memory_kib must be at least kdf_memory_kib")
        if self.max_delay_s < self.base_delay_s:
            raise ValueError("max_delay_s must be at least base_delay_s")
        return self


class ConnectSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    oauth_attempt_ttl_s: int = Field(
        default=600,
        ge=5,
        le=3600,
        description="Seconds an OAuth attempt stays valid.",
    )
    oauth_timeout_s: float = Field(
        default=15.0,
        gt=0,
        le=120,
        description="Seconds to wait for OAuth network calls.",
    )
    imap_timeout_s: float = Field(
        default=15.0,
        gt=0,
        le=120,
        description="Seconds to wait for IMAP network calls.",
    )
    token_refresh_margin_s: int = Field(
        default=120,
        ge=0,
        le=3600,
        description="Seconds before expiry to refresh an access token.",
    )
    shutdown_join_s: float = Field(
        default=2.0,
        gt=0,
        le=30,
        description="Seconds to wait for OAuth flows to stop.",
    )
    auth_check_concurrency: int = Field(
        default=4,
        ge=1,
        le=16,
        description="Accounts checked in parallel after vault unlock.",
    )


class InboundSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["auto", "imap", "gmail_api"] = Field(
        default="auto",
        description=(
            "Default inbound owner. auto keeps IMAP for every auth kind and "
            "uses the Gmail API only as the completeness sweep."
        ),
    )
    ingest_since_init: bool = Field(
        default=True,
        description=(
            "Only ingest messages dated on or after this installation was "
            "first initialized. Turn this off to backfill older mail up to "
            "the configured initial-sync window."
        ),
    )
    api_poll_s: float = Field(
        default=60.0,
        ge=10,
        le=300,
        description="Seconds between Gmail API history polls when it owns an account.",
    )
    sweep_tick_s: float = Field(
        default=60.0,
        ge=10,
        le=3600,
        description=(
            "Base gap between fleet sweep slots. This is not a per-account interval."
        ),
    )
    sweep_slot_jitter: float = Field(
        default=0.25,
        ge=0,
        le=0.5,
        description="Fraction of sweep_tick_s added randomly to each slot.",
    )
    sweep_accounts_per_tick: int = Field(
        default=1,
        ge=1,
        le=5,
        description="Accounts swept sequentially in one slot.",
    )
    sweep_initial_days: int = Field(
        default=7,
        ge=0,
        le=3650,
        description="Backfill window on the first Gmail API sync or sweep.",
    )
    sweep_limit: int = Field(
        default=500,
        ge=1,
        le=5000,
        description="Messages fetched per Gmail API sweep or backfill.",
    )
    idle_fleet_cap: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Accounts allowed to hold an IMAP IDLE connection.",
    )
    idle_heartbeat_s: float = Field(
        default=60.0,
        ge=30,
        le=1740,
        description="Maximum IDLE silence before a NOOP liveness check.",
    )
    idle_timeout_s: float = Field(
        default=1500.0,
        ge=10,
        le=1740,
        description="Seconds an IMAP IDLE connection waits before reconnecting.",
    )
    poll_interval_s: float = Field(
        default=300.0,
        ge=5,
        le=3600,
        description="Seconds between polls when IDLE is unavailable.",
    )
    initial_sync_days: int = Field(
        default=7,
        ge=0,
        le=3650,
        description="Days of mail to fetch on the first sync.",
    )
    initial_sync_limit: int = Field(
        default=500,
        ge=1,
        le=100_000,
        description="Maximum messages to fetch on the first sync.",
    )
    body_max_bytes: int = Field(
        default=2_097_152,
        ge=1024,
        le=268_435_456,
        description="Maximum body bytes stored per inbound message.",
    )
    fetch_batch: int = Field(
        default=25,
        ge=1,
        le=500,
        description="Messages fetched per IMAP batch.",
    )
    ingest_timeout_s: float = Field(
        default=60.0,
        gt=0,
        le=600,
        description="Seconds to wait for inbound ingestion.",
    )
    backoff_s: list[int] = Field(
        default_factory=lambda: [5, 15, 60, 300, 900],
        min_length=1,
        max_length=16,
        description="Retry delays in seconds for inbound failures.",
    )
    shutdown_join_s: float = Field(
        default=2.0,
        gt=0,
        le=30,
        description="Seconds to wait for watcher threads to stop.",
    )

    @field_validator("backoff_s")
    @classmethod
    def ordered_backoff(cls, value: list[int]) -> list[int]:
        if any(item < 1 for item in value):
            raise ValueError("backoff values must be positive seconds")
        if value != sorted(value):
            raise ValueError("backoff values must be in ascending order")
        return value


class OutboundSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    smtp_timeout_s: float = Field(
        default=30.0,
        gt=0,
        le=300,
        description="Seconds to wait for SMTP network calls.",
    )
    api_timeout_s: float = Field(
        default=60.0,
        gt=0,
        le=300,
        description="Seconds to wait for Gmail API requests.",
    )
    lease_seconds: int = Field(
        default=120,
        ge=10,
        le=3600,
        description="Seconds a job lease is held while sending.",
    )
    reconcile_attempts: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Sent-folder searches after an uncertain send.",
    )
    reconcile_delay_s: float = Field(
        default=1.0,
        ge=0,
        le=60,
        description="Seconds between Sent-folder searches.",
    )
    keepalive: bool = Field(
        default=True,
        description="Keep SMTP sessions open and reuse them for later sends.",
    )
    keepalive_idle_s: int = Field(
        default=300,
        ge=5,
        le=3600,
        description="Seconds an idle SMTP session is kept before it is closed.",
    )
    keepalive_max_sessions: int = Field(
        default=1,
        ge=1,
        le=16,
        description="SMTP sessions kept open per binding.",
    )
    keepalive_noop_s: int = Field(
        default=60,
        ge=1,
        le=3600,
        description="Seconds before a reused session is checked with NOOP.",
    )


class IntakeSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_messages: int = Field(
        default=10_000,
        ge=1,
        le=1_000_000,
        description="Maximum messages in one campaign.",
    )
    max_body_bytes: int = Field(
        default=1_000_000,
        ge=1024,
        le=26_214_400,
        description="Maximum body bytes per campaign message.",
    )
    max_attachment_bytes: int = Field(
        default=26_214_400,
        ge=1024,
        le=104_857_600,
        description="Maximum bytes per campaign attachment.",
    )
    max_file_bytes: int = Field(
        default=67_108_864,
        ge=1024,
        le=536_870_912,
        description="Maximum input file size in bytes.",
    )
    sample_count: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of sample recipients in a review batch.",
    )


class ConfigSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reload_check_s: float = Field(
        default=0.5,
        ge=0.05,
        le=60,
        description="Seconds between checks of config.toml for hand edits.",
    )
