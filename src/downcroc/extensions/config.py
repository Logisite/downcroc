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
    max_restarts: int = Field(default=3, ge=0, le=100)
    call_timeout_s: float = Field(default=30.0, gt=0, le=600)
    max_calls_per_min: int = Field(default=120, ge=1, le=100_000)
    max_sends_per_hour: int = Field(default=200, ge=1, le=100_000)


class ExtensionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    trust: bool = False
    allow: list[str] = Field(default_factory=list)
    settings: dict[str, Any] = Field(default_factory=dict)


def parse_grant(value: str) -> tuple[str, str | None]:
    head, _, tail = value.partition(":")
    return head, tail or None
