from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from downcroc.runtime.config.schema_common import LOOPBACK, RESTART


class DaemonSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    host: str = Field(
        default="127.0.0.1",
        description="Loopback address the HTTP API binds to.",
        json_schema_extra=RESTART,
    )
    port: int = Field(
        default=8765,
        ge=1024,
        le=65535,
        description="TCP port for the HTTP API.",
        json_schema_extra=RESTART,
    )
    start_timeout_s: float = Field(
        default=10.0,
        gt=0,
        le=120,
        description="Seconds to wait for a detached daemon to become healthy.",
    )
    stop_timeout_s: float = Field(
        default=15.0,
        gt=0,
        le=120,
        description="Seconds to wait for a daemon to stop before killing it.",
    )

    @field_validator("host")
    @classmethod
    def loopback_only(cls, value: str) -> str:
        if value not in LOOPBACK:
            raise ValueError("must be a loopback address")
        return value


class LoggingSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: Literal["debug", "info", "warning", "error"] = Field(
        default="info",
        description="Minimum log level written to the daemon log.",
    )
    max_bytes: int = Field(
        default=10_485_760,
        ge=65_536,
        description="Maximum size of one log file before rotation.",
        json_schema_extra=RESTART,
    )
    backups: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of rotated log files to keep.",
        json_schema_extra=RESTART,
    )


class SendingSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    daily_allowance: int = Field(
        default=200,
        ge=1,
        le=100_000,
        description="Maximum messages sent per account per local day.",
    )
    window_start: int = Field(
        default=0,
        ge=0,
        le=23,
        description="First local hour when sending is allowed, inclusive.",
    )
    window_end: int = Field(
        default=24,
        ge=1,
        le=24,
        description="Last local hour when sending is allowed, exclusive.",
    )
    jitter_min: int = Field(
        default=30,
        ge=0,
        le=3600,
        description="Minimum seconds between sends on one account.",
    )
    jitter_max: int = Field(
        default=90,
        ge=0,
        le=3600,
        description="Maximum seconds between sends on one account.",
    )
    max_in_flight: int = Field(
        default=2,
        ge=1,
        le=64,
        description="Maximum concurrent sends per account.",
    )
    enabled: bool = Field(
        default=True,
        description="Whether automatic sending is enabled.",
    )

    @model_validator(mode="after")
    def ordered_jitter(self) -> SendingSettings:
        if self.jitter_max < self.jitter_min:
            raise ValueError("jitter_max must be at least jitter_min")
        if self.window_start == self.window_end:
            raise ValueError("window_start and window_end must differ")
        return self


class DispatchSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tick_s: float = Field(
        default=2.0,
        ge=0.05,
        le=60,
        description="Seconds between dispatcher cycles.",
    )
    max_attempts: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum send attempts before a job is failed.",
    )
    retry_base_s: int = Field(
        default=30,
        ge=1,
        le=3600,
        description="Base delay in seconds for retry backoff.",
    )
    retry_factor: float = Field(
        default=2.0,
        ge=1.0,
        le=10.0,
        description="Multiplier applied to the retry delay.",
    )
    retry_cap_s: int = Field(
        default=3600,
        ge=1,
        le=86_400,
        description="Maximum retry delay in seconds.",
    )
    retry_jitter: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Fraction of retry delay applied as random spread.",
    )
    global_in_flight: int = Field(
        default=8,
        ge=1,
        le=256,
        description="Maximum concurrent sends across all accounts.",
    )
    shutdown_join_s: float = Field(
        default=5.0,
        gt=0,
        le=30,
        description="Seconds to wait for a dispatcher cycle to stop.",
    )

    @model_validator(mode="after")
    def ordered_retries(self) -> DispatchSettings:
        if self.retry_cap_s < self.retry_base_s:
            raise ValueError("retry_cap_s must be at least retry_base_s")
        return self


class FollowUpSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_s: float = Field(
        default=30.0,
        ge=0.05,
        le=3600,
        description="Seconds between follow-up planning cycles.",
    )
    sync_timeout_s: float = Field(
        default=30.0,
        gt=0,
        le=300,
        description="Seconds to wait for a mailbox sync before planning.",
    )
    defer_s: float = Field(
        default=300.0,
        ge=1,
        le=86_400,
        description="Seconds to defer a follow-up when its parent is not ready.",
    )


class RetentionSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_s: float = Field(
        default=3600.0,
        ge=0.05,
        le=86_400,
        description="Seconds between retention passes.",
    )
    jobs_days: int = Field(
        default=30,
        ge=1,
        le=3650,
        description="Days to keep finished jobs.",
    )
    jobs_max: int = Field(
        default=10_000,
        ge=1,
        le=1_000_000,
        description="Maximum finished jobs to keep.",
    )
    mail_days: int = Field(
        default=90,
        ge=1,
        le=3650,
        description="Days to keep inbound messages.",
    )
    hourly_days: int = Field(
        default=90,
        ge=1,
        le=3650,
        description="Days to keep hourly activity rows.",
    )
    daily_days: int = Field(
        default=730,
        ge=1,
        le=3650,
        description="Days to keep daily activity rows.",
    )
