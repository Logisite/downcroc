from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AttemptKind(StrEnum):
    OAUTH = "oauth"


class AttemptState(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"

    @property
    def terminal(self) -> bool:
        return self is not AttemptState.PENDING


@dataclass(frozen=True)
class ConnectAttempt:
    id: str
    account_id: str
    kind: AttemptKind
    state: AttemptState
    authorization_url: str
    state_token: str
    callback_port: int
    created_at: str
    expires_at: str
    error: str | None


class HoleStatus(StrEnum):
    MISSING = "missing"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class ThreadHole:
    """A sent attempt whose Gmail provider thread id is still missing."""

    attempt_id: str
    job_id: str
    account_id: str
    message_id: str
    started_at: str
    provider_message_id: str | None = None
    outcome: str = "sent"
    first_miss_at: str | None = None
    next_check_at: str | None = None
    check_count: int = 0
    last_result: str | None = None
    thread_status: str | None = None


@dataclass(frozen=True)
class SendAttempt:
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
    provider_thread_id: str | None = None
    detail: str | None = None
    quota_day: str | None = None
    quota_state: str | None = None
