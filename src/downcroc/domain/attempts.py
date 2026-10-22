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
