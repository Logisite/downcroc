from __future__ import annotations

from dataclasses import dataclass

from downcroc.domain.accounts import Account
from downcroc.domain.providers import AuthKind, ProviderSpec

IMAP = "imap"
GMAIL_API = "gmail_api"


@dataclass(frozen=True)
class SourceChoice:
    source: str
    mode: str
    reason: str
    requested: str


def requested_source(account: Account, default: str) -> str:
    value = account.source_override or default
    if value in {IMAP, GMAIL_API}:
        return value
    return "auto"


def choose_source(
    account: Account,
    spec: ProviderSpec,
    default: str,
    *,
    allow_idle: bool,
) -> SourceChoice:
    wanted = requested_source(account, default)
    if wanted == GMAIL_API and _api_allowed(spec):
        return SourceChoice(GMAIL_API, "api_poll", "override", wanted)
    reason = "auto" if wanted == "auto" else "api_unavailable"
    if wanted == GMAIL_API and not _api_allowed(spec):
        reason = "api_unavailable"
    if spec.supports_idle and allow_idle:
        return SourceChoice(IMAP, "idle", reason, wanted)
    return SourceChoice(IMAP, "imap_poll", reason, wanted)


def owner_label(source: str, mode: str) -> str:
    if source == GMAIL_API:
        return "gmail_api poll"
    return f"imap {mode if mode in {'idle', 'imap_poll'} else 'poll'}"


def _api_allowed(spec: ProviderSpec) -> bool:
    return spec.auth_kind is AuthKind.OAUTH2 and spec.api_configured
