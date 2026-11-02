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


class JobDeleteOut(BaseModel):
    job_id: str
    batch_id: str
    state: str
    bytes: int = 0
    dry_run: bool = False


class JobDeletionCounts(BaseModel):
    jobs: int = 0
    queued: int = 0
    awaiting_approval: int = 0
    retry_wait: int = 0
    sending: int = 0
    sent: int = 0
    failed: int = 0
    cancelled: int = 0


class JobDeletionOut(BaseModel):
    account_id: str | None
    state: str | None
    counts: JobDeletionCounts
    blockers: list[str]


class ReassignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_account_id: str | None = Field(default=None, max_length=64)
    to_account_id: str | None = Field(default=None, max_length=64)
    job_ids: list[str] = Field(default_factory=list, max_length=10_000)
    batch_ids: list[str] = Field(default_factory=list, max_length=10_000)
    states: list[str] = Field(default_factory=list, max_length=16)
    created_since: str | None = None
    created_until: str | None = None
    include_failed: bool = False
    pin: bool = False
    unpin: bool = False
    force: bool = False
    dry_run: bool = False
    confirm: bool = False


class ReassignSkipped(BaseModel):
    id: str
    reason: str


class ReassignOut(BaseModel):
    jobs: int
    batches: int
    skipped: list[ReassignSkipped]
    pinned: int = 0
    unpinned: int = 0
    dry_run: bool


class SendAttemptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    account_id: str | None
    binding_id: str | None
    transport: str
    started_at: str
    finished_at: str | None
    outcome: str
    accepted: bool | None
    error_code: str | None
    error_message: str | None
    provider_message_id: str | None


class JobErrorOut(BaseModel):
    code: str
    message: str
    retryable: bool | None


class JobOut(BaseModel):
    id: str
    batch_id: str
    account_id: str | None
    sender_policy: str
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
    eta: dict[str, object] | None = None

    @classmethod
    def of(cls, job: Job, eta: dict[str, object] | None = None) -> JobOut:
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
            sender_policy=job.sender_policy.value,
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
            eta=eta,
        )
