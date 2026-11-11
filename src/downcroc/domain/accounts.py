from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from downcroc.domain.policy import PolicyOverride


class AccountStatus(StrEnum):
    PENDING = "pending"
    UNVERIFIED = "unverified"
    CONNECTED = "connected"
    NEEDS_REAUTH = "needs_reauth"
    DISABLED = "disabled"


@dataclass(frozen=True)
class Account:
    id: str
    provider: str
    address: str
    label: str
    status: AccountStatus
    created_at: str
    last_verified_at: str | None
    policy: PolicyOverride
    last_error: str | None = None
    credential_key: str | None = None
    archived_at: str | None = None
    watcher_enabled: bool = True
    last_uid: int = 0
    uidvalidity: int = 0
    last_sync_at: str | None = None
    consecutive_failures: int = 0
    source_override: str | None = None
    inbound_source: str | None = None
    history_id: str | None = None
    cursor_source: str | None = None
    last_sweep_at: str | None = None
    last_source_switch_at: str | None = None
    paused_at: str | None = None
    paused_reason: str | None = None
    auth_checked_at: str | None = None
    auth_status: str | None = None
    auth_error: str | None = None
    auth_action: str | None = None
