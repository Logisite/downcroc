from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from downcroc.runtime.clock import zone_for
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
        default=60.0,
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
    enforcement_mode: Literal["permissive", "strict"] = Field(
        default="permissive",
        description="Permissive lets account overrides win; strict uses the global values.",
    )
    timezone: str = Field(
        default="UTC",
        description="IANA name or UTC offset like +1 or -3 used for the send day.",
    )

    @field_validator("timezone")
    @classmethod
    def known_timezone(cls, value: str) -> str:
        try:
            zone_for(value)
        except (KeyError, ValueError) as error:
            raise ValueError(
                "timezone must be an IANA name like UTC or an offset like +1"
            ) from error
        return value

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
    parallel_sends: bool = Field(
        default=False,
        description=(
            "Allow more than one send in flight. Off by default; one send at a "
            "time is the recommended and safest mode."
        ),
    )
    api_max_concurrency: int = Field(
        default=1,
        ge=1,
        le=16,
        description=(
            "Maximum parallel Gmail API sends when parallel_sends is on. "
            "Ignored while parallel_sends is off."
        ),
    )
    smtp_seats: int = Field(
        default=1,
        ge=1,
        le=10,
        description=(
            "Distinct SMTP mailboxes in the serial send rotation. This is not "
            "parallel sending. Values above 3 are risky and strongly warned."
        ),
    )
    network_cooldown_after: int = Field(
        default=2,
        ge=1,
        le=20,
        description="Consecutive network failures before a binding cools down.",
    )
    network_cooldown_s: int = Field(
        default=60,
        ge=1,
        le=86_400,
        description="Base cool-down in seconds after a network failure.",
    )
    quota_cooldown_s: int = Field(
        default=300,
        ge=1,
        le=86_400,
        description="Cool-down in seconds when a provider reports quota limits.",
    )
    capacity_advice: bool = Field(
        default=True,
        description="Warn when a selection runs on a single sequential seat.",
    )
    capacity_warn_messages: int = Field(
        default=10,
        ge=1,
        le=100_000,
        description="Message count at which capacity advice becomes a warning.",
    )
    capacity_warn_on_window: bool = Field(
        default=True,
        description="Escalate when an estimate spills past the send window.",
    )
    eta_horizon_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Days the finish estimate may walk before reporting beyond_horizon.",
    )
    eta_refresh_s: float = Field(
        default=30.0,
        ge=0.5,
        le=3600,
        description="Minimum seconds between interactive ETA recomputations.",
    )
    pause_max_s: int = Field(
        default=2_592_000,
        ge=1,
        le=31_536_000,
        description="Maximum duration accepted by service pause --for.",
    )
    pause_reason_max: int = Field(
        default=200,
        ge=1,
        le=2000,
        description="Maximum characters stored in a pause reason.",
    )
    seat_hole_warn: bool = Field(
        default=True,
        description="Warn when a pause drops throughput or holds pinned work.",
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


class CliSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timeout_s: float = Field(
        default=10.0,
        gt=0,
        le=60,
        description="Seconds a CLI request waits for the daemon.",
    )
    page_lines: int = Field(
        default=40,
        ge=0,
        le=10_000,
        description="Lines before interactive output is paged; 0 disables paging.",
    )
    glyphs: Literal["auto", "nerd", "ascii"] = Field(
        default="auto",
        description="Glyph set: auto, nerd, or ascii.",
    )
    tables: bool = Field(
        default=True,
        description=(
            "Always draw boxed tables. Set false to fall back to stacked fields "
            "when the terminal is too narrow for the grid."
        ),
    )
