from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from downcroc.domain.jobs import Job


class JobCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str = Field(min_length=1, max_length=64)
    recipient: str = Field(min_length=3, max_length=320)
    recipient_name: str | None = Field(default=None, max_length=200)
    subject: str = Field(min_length=1, max_length=1000)
    text: str = Field(default="", max_length=1_000_000)
    html: str | None = Field(default=None, max_length=1_000_000)
    batch_id: str = Field(default="manual", min_length=1, max_length=64)


class JobErrorOut(BaseModel):
    code: str
    message: str
    retryable: bool | None


class JobOut(BaseModel):
    id: str
    batch_id: str
    account_id: str
    recipient: str
    recipient_name: str | None
    source_kind: str
    source_key: str | None
    source_index: int
    step_key: str | None
    parent_job_id: str | None
    thread_root_job_id: str | None
    subject: str
    body_ref: str
    state: str
    attempts: int
    next_attempt_at: str | None
    message_id: str
    last_error: JobErrorOut | None
    created_at: str
    updated_at: str
    sent_at: str | None

    @classmethod
    def of(cls, job: Job) -> JobOut:
        error = None
        if job.last_error_code is not None:
            error = JobErrorOut(
                code=job.last_error_code,
                message=job.last_error_message or "",
                retryable=job.retryable,
            )
        return cls(
            id=job.id,
            batch_id=job.batch_id,
            account_id=job.account_id,
            recipient=job.recipient,
            recipient_name=job.recipient_name,
            source_kind=job.source_kind,
            source_key=job.source_key,
            source_index=job.source_index,
            step_key=job.step_key,
            parent_job_id=job.parent_job_id,
            thread_root_job_id=job.thread_root_job_id,
            subject=job.subject,
            body_ref=job.body_ref,
            state=job.state.value,
            attempts=job.attempts,
            next_attempt_at=job.next_attempt_at,
            message_id=job.message_id,
            last_error=error,
            created_at=job.created_at,
            updated_at=job.updated_at,
            sent_at=job.sent_at,
        )
