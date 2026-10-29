from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from downcroc.domain.failures import FailedJob


class FailureOut(BaseModel):
    job_id: str
    batch_id: str
    account_id: str | None
    recipient: str
    code: str
    message: str
    retryable: bool | None
    attempts: int
    failed_at: str

    @classmethod
    def of(cls, failure: FailedJob) -> FailureOut:
        return cls(
            job_id=failure.job_id,
            batch_id=failure.batch_id,
            account_id=failure.account_id,
            recipient=failure.recipient,
            code=failure.code,
            message=failure.message,
            retryable=failure.retryable,
            attempts=failure.attempts,
            failed_at=failure.failed_at,
        )


class FailureRetryAll(BaseModel):
    retried: int


class FailureForgetOut(BaseModel):
    job_id: str
    forgotten: bool


class FailurePurgeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    states: list[str] = Field(default_factory=list, max_length=16)
    older_than_days: int | None = Field(default=None, ge=0)
    dry_run: bool = False
    confirm: bool = False


class FailurePurgeOut(BaseModel):
    failures: int
    dry_run: bool
