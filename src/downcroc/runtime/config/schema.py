from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

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


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    daemon: DaemonSettings = Field(default_factory=DaemonSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
