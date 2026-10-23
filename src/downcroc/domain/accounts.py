from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AccountStatus(StrEnum):
    PENDING = "pending"
    UNVERIFIED = "unverified"
    CONNECTED = "connected"
    NEEDS_REAUTH = "needs_reauth"
    DISABLED = "disabled"


@dataclass(frozen=True)
class SendPolicy:
    daily_allowance: int
    window_start: int
    window_end: int
    jitter_min: int
    jitter_max: int
    max_in_flight: int
    enabled: bool


@dataclass(frozen=True)
class Account:
    id: str
    provider: str
    address: str
    label: str
    status: AccountStatus
    credential_present: bool
    created_at: str
    last_verified_at: str | None
    policy: SendPolicy
    last_error: str | None = None
    credential_key: str | None = None
    watcher_enabled: bool = True
    last_uid: int = 0
    uidvalidity: int = 0
    last_sync_at: str | None = None
    consecutive_failures: int = 0
