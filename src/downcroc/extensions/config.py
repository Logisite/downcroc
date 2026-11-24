from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ExtensionSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(
        default=True,
        description="Enable the extension system.",
    )
    dir: str = Field(
        default="extensions",
        description="Directory under the config home holding extension manifests.",
    )
    max_restarts: int = Field(
        default=3,
        ge=0,
        le=100,
        description="Restart ceiling for a crashed extension.",
    )
    max_protocol_rounds: int = Field(
        default=8,
        ge=1,
        le=64,
        description="Maximum action rounds for one extension event.",
    )
    call_timeout_s: float = Field(
        default=30.0,
        gt=0,
        le=600,
        description="Seconds an extension may take to answer one event.",
    )
    max_calls_per_min: int = Field(
        default=120,
        ge=1,
        le=100_000,
        description="Per-extension capability call limit per minute.",
    )
    notifier: list[str] = Field(
        default_factory=list,
        description="Command used by notify.system; title and message are appended.",
    )
    max_sends_per_hour: int = Field(
        default=200,
        ge=1,
        le=100_000,
        description="Per-extension mail action limit per hour.",
    )


class ExtensionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    trust: bool = False
    allow: list[str] = Field(default_factory=list)
    settings: dict[str, Any] = Field(default_factory=dict)


def parse_grant(value: str) -> tuple[str, str | None]:
    head, _, tail = value.partition(":")
    return head, tail or None
