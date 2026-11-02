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
    detail: str | None
    quota_day: str | None = None
    quota_state: str | None = None
