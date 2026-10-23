from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

LOOPBACK = frozenset({"127.0.0.1", "::1", "localhost"})


class DaemonSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    host: str = "127.0.0.1"
    port: int = Field(default=8765, ge=1024, le=65535)
    start_timeout_s: float = Field(default=10.0, gt=0, le=120)
    stop_timeout_s: float = Field(default=15.0, gt=0, le=120)

    @field_validator("host")
    @classmethod
    def loopback_only(cls, value: str) -> str:
        if value not in LOOPBACK:
            raise ValueError("must be a loopback address")
        return value


class LoggingSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: Literal["debug", "info", "warning", "error"] = "info"
    max_bytes: int = Field(default=10_485_760, ge=65_536)
    backups: int = Field(default=5, ge=1, le=50)


class SendingSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    daily_allowance: int = Field(default=200, ge=1, le=100_000)
    window_start: int = Field(default=0, ge=0, le=23)
    window_end: int = Field(default=24, ge=1, le=24)
    jitter_min: int = Field(default=30, ge=0, le=3600)
    jitter_max: int = Field(default=90, ge=0, le=3600)
    max_in_flight: int = Field(default=2, ge=1, le=64)
    enabled: bool = True

    @model_validator(mode="after")
    def ordered_jitter(self) -> SendingSettings:
        if self.jitter_max < self.jitter_min:
            raise ValueError("jitter_max must be at least jitter_min")
        return self


class EventsSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ring_size: int = Field(default=10_000, ge=1, le=1_000_000)
    queue_size: int = Field(default=1000, ge=16, le=100_000)
    keepalive_s: float = Field(default=15.0, gt=0, le=300)


class VaultSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kdf_memory_kib: int = Field(default=65_536, ge=8192, le=1_048_576)
    kdf_iterations: int = Field(default=3, ge=1, le=10)
    kdf_lanes: int = Field(default=1, ge=1, le=8)
    kdf_target_ms: int = Field(default=250, ge=50, le=2000)
    kdf_max_memory_kib: int = Field(default=262_144, ge=8192, le=1_048_576)
    free_attempts: int = Field(default=5, ge=0, le=100)
    base_delay_s: float = Field(default=1.0, gt=0, le=60)
    max_delay_s: float = Field(default=300.0, ge=1, le=3600)

    @model_validator(mode="after")
    def ordered_vault(self) -> VaultSettings:
        if self.kdf_max_memory_kib < self.kdf_memory_kib:
            raise ValueError("kdf_max_memory_kib must be at least kdf_memory_kib")
        if self.max_delay_s < self.base_delay_s:
            raise ValueError("max_delay_s must be at least base_delay_s")
        return self


class ConnectSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    oauth_attempt_ttl_s: int = Field(default=600, ge=5, le=3600)
    oauth_timeout_s: float = Field(default=15.0, gt=0, le=120)
    imap_timeout_s: float = Field(default=15.0, gt=0, le=120)
    token_refresh_margin_s: int = Field(default=120, ge=0, le=3600)
    shutdown_join_s: float = Field(default=2.0, gt=0, le=30)


class InboundSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idle_timeout_s: float = Field(default=1500.0, ge=10, le=1740)
    poll_interval_s: float = Field(default=300.0, ge=5, le=3600)
    initial_sync_days: int = Field(default=7, ge=0, le=3650)
    initial_sync_limit: int = Field(default=500, ge=1, le=100_000)
    body_max_bytes: int = Field(default=2_097_152, ge=1024, le=268_435_456)
    fetch_batch: int = Field(default=25, ge=1, le=500)
    ingest_timeout_s: float = Field(default=60.0, gt=0, le=600)
    backoff_s: list[int] = Field(
        default_factory=lambda: [5, 15, 60, 300, 900],
        min_length=1,
        max_length=16,
    )
    shutdown_join_s: float = Field(default=2.0, gt=0, le=30)

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

    smtp_timeout_s: float = Field(default=30.0, gt=0, le=300)
    lease_seconds: int = Field(default=120, ge=10, le=3600)
    reconcile_attempts: int = Field(default=3, ge=1, le=10)
    reconcile_delay_s: float = Field(default=1.0, ge=0, le=60)


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    daemon: DaemonSettings = Field(default_factory=DaemonSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    sending: SendingSettings = Field(default_factory=SendingSettings)
    events: EventsSettings = Field(default_factory=EventsSettings)
    vault: VaultSettings = Field(default_factory=VaultSettings)
    connect: ConnectSettings = Field(default_factory=ConnectSettings)
    inbound: InboundSettings = Field(default_factory=InboundSettings)
    outbound: OutboundSettings = Field(default_factory=OutboundSettings)
