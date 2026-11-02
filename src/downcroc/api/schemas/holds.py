from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PauseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=2000)
    for_s: int | None = Field(default=None, ge=1)


class ResumeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=2000)


class AllPauseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    all: bool = False
    reason: str | None = Field(default=None, max_length=2000)
