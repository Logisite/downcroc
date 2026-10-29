from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TransportKind(StrEnum):
    SMTP = "smtp"
    GMAIL_API = "gmail_api"


class TransportHealth(StrEnum):
    READY = "ready"
    COOLING_DOWN = "cooling_down"
    QUOTA_EXHAUSTED = "quota_exhausted"
    NEEDS_REAUTH = "needs_reauth"
    DISABLED = "disabled"


@dataclass(frozen=True)
class AccountTransport:
    id: str
    account_id: str
    provider_id: str
    kind: TransportKind
    credential_ref: str | None
    oauth_client_id: str | None
    enabled: bool
    priority: int
    max_concurrency: int
    rate_per_min: int | None
    health: TransportHealth
    cooldown_until: str | None
    last_error_code: str | None
    last_error_message: str | None
    last_success_at: str | None
    created_at: str
    updated_at: str

    @property
    def seat(self) -> bool:
        return self.kind is TransportKind.SMTP


@dataclass(frozen=True)
class OAuthClient:
    id: str
    provider_id: str
    label: str
    client_id: str
    project_id: str | None
    secret_ref: str
    created_at: str
    updated_at: str
