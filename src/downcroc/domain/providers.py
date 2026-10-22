from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AuthKind(StrEnum):
    OAUTH2 = "oauth2"
    APP_PASSWORD = "app_password"
    NONE = "none"


class TlsMode(StrEnum):
    SSL = "ssl"
    STARTTLS = "starttls"
    NONE = "none"


@dataclass(frozen=True)
class ProviderSpec:
    id: str
    label: str
    imap_host: str
    imap_port: int
    imap_tls: TlsMode
    smtp_host: str
    smtp_port: int
    smtp_tls: TlsMode
    auth_kind: AuthKind
    smtp_auth_mechanism: str
    sent_folder: str
    supports_idle: bool
    requires_user_agent: bool
    attachment_max_bytes: int
    notes: str
    oauth_authorize_url: str = ""
    oauth_token_url: str = ""
    oauth_scopes: tuple[str, ...] = ()
    oauth_client_id: str = ""
    oauth_client_secret: str = ""
    oauth_tenant: str = "common"
    oauth_extra_params: tuple[tuple[str, str], ...] = ()

    @property
    def oauth_configured(self) -> bool:
        return bool(self.oauth_client_id)

    @property
    def imap_configured(self) -> bool:
        return bool(self.imap_host and self.imap_port)

    def oauth_url(self, value: str) -> str:
        return value.replace("{tenant}", self.oauth_tenant)
