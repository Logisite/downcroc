from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from downcroc.core.followups.status import StatusReport, StepStatus


class FollowUpDeclareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1, max_length=4096)
    kind: Literal["shared", "payload"] | None = None
    version: int | None = Field(default=None, ge=1)
    dry_run: bool = False


class FollowUpStepOut(BaseModel):
    step: str
    kind: str
    state: str
    after_days: int
    when: str
    require_approval: bool
    version: int | None
    child_batch_id: str | None
    counts: dict[str, int]
    detail: str | None = None

    @classmethod
    def of(cls, row: StepStatus) -> FollowUpStepOut:
        return cls(
            step=row.step,
            kind=row.kind,
            state=row.state,
            after_days=row.after_days,
            when=row.when,
            require_approval=row.require_approval,
            version=row.version,
            child_batch_id=row.child_batch_id,
            counts=row.counts,
            detail=row.detail,
        )


class FollowUpStatusOut(BaseModel):
    batch_id: str
    steps: list[FollowUpStepOut]
    dry_run: bool = False
    changed: bool = False

    @classmethod
    def of(cls, report: StatusReport) -> FollowUpStatusOut:
        return cls(
            batch_id=report.batch_id,
            steps=[FollowUpStepOut.of(row) for row in report.steps],
            dry_run=report.dry_run,
            changed=report.changed,
        )
