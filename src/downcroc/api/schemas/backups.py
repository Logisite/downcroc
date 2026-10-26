from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from downcroc.backup.bundle import BackupResult
from downcroc.backup.restore import RestoreOutcome


class BackupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    include_logs: bool = False


class BackupOut(BaseModel):
    path: str
    files: int
    bytes: int
    duration_ms: int
    schema_revision: str
    counts: dict[str, int]

    @classmethod
    def of(cls, result: BackupResult) -> BackupOut:
        return cls(
            path=str(result.path),
            files=result.files,
            bytes=result.bytes,
            duration_ms=result.duration_ms,
            schema_revision=result.manifest.schema_revision,
            counts=result.manifest.counts,
        )


class RestoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)


class RestorePendingOut(BaseModel):
    status: Literal["pending"] = "pending"
    bundle: str
    marker: str
    files: int
    schema_revision: str
    counts: dict[str, int]
    restart_required: bool = True

    @classmethod
    def of(cls, outcome: RestoreOutcome) -> RestorePendingOut:
        return cls(
            bundle=str(outcome.bundle or "unknown"),
            marker=str(outcome.marker),
            files=outcome.files,
            schema_revision=outcome.revision or "none",
            counts=outcome.counts,
        )
