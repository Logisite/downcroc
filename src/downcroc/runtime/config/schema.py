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


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    daemon: DaemonSettings = Field(default_factory=DaemonSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    sending: SendingSettings = Field(default_factory=SendingSettings)
    events: EventsSettings = Field(default_factory=EventsSettings)
