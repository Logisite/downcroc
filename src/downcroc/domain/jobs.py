from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class JobState(StrEnum):
    QUEUED = "queued"
    AWAITING_APPROVAL = "awaiting_approval"
    SENDING = "sending"
    SENT = "sent"
    SENT_UNCONFIRMED = "sent_unconfirmed"
    RETRY_WAIT = "retry_wait"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SenderPolicy(StrEnum):
    PINNED = "pinned"
    AUTO = "auto"


@dataclass(frozen=True)
class Job:
    id: str
    batch_id: str
    account_id: str | None
    sender_policy: SenderPolicy
    recipient: str
    recipient_name: str | None
    source_kind: str
    source_key: str | None
    source_index: int
    step_key: str | None
    parent_job_id: str | None
    thread_root_job_id: str | None
    vars_json: str
    subject: str
    body_ref: str
    state: JobState
    attempts: int
    next_attempt_at: str | None
    lease_owner: str | None
    lease_expires_at: str | None
    message_id: str
    last_error_code: str | None
    last_error_message: str | None
    retryable: bool | None
    created_at: str
    updated_at: str
    sent_at: str | None


@dataclass(frozen=True)
class NewJob:
    id: str
    batch_id: str
    account_id: str | None
    recipient: str
    recipient_name: str | None
    vars_json: str
    subject: str
    body_ref: str
    message_id: str
    created_at: str
    source_kind: str = "manual"
    sender_policy: SenderPolicy = SenderPolicy.PINNED
    source_key: str | None = None
    source_index: int = 0
    step_key: str | None = None
    parent_job_id: str | None = None
    thread_root_job_id: str | None = None
    state: JobState = JobState.QUEUED
