from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from downcroc.domain.errors import ProviderConfigError
from downcroc.domain.providers import AuthKind, ProviderSpec, TlsMode

REQUIRED = frozenset({"id", "label", "imap_host", "imap_port", "imap_tls", "auth_kind"})
API_TRANSPORTS = frozenset({"smtp", "gmail_api"})
_STRING_FIELDS = (
    "smtp_host",
    "smtp_auth_mechanism",
    "sent_folder",
    "notes",
    "oauth_authorize_url",
    "oauth_token_url",
    "oauth_client_id",
    "oauth_client_secret",
    "oauth_tenant",
    "transport",
    "api_base_url",
)
_INT_FIELDS = (
    "imap_port",
    "smtp_port",
    "attachment_max_bytes",
    "api_max_concurrency",
    "api_rate_per_min",
)


def parse_spec(
    provider_id: str,
    values: dict[str, Any],
    path: Path | None,
) -> ProviderSpec:
    missing = sorted(REQUIRED - set(values))
    if missing:
        raise ProviderConfigError(
            "a declaration is incomplete", path=path, field=missing[0]
        )
    _check_types(values, path)
    imap_tls = _tls(values["imap_tls"], path, "imap_tls")
    smtp_tls = _tls(values.get("smtp_tls", "starttls"), path, "smtp_tls")
    auth_kind = _auth(values["auth_kind"], path)
    scopes = _strings(values.get("oauth_scopes", []), path, "oauth_scopes")
    api_scopes = _strings(values.get("api_scopes", []), path, "api_scopes")
    extra = _table(values.get("oauth_extra_params", {}), path)
    transport = values.get("transport", "smtp")
    if transport not in API_TRANSPORTS:
        raise ProviderConfigError(
            "field has an unknown value", path=path, field="transport"
        )
    api_base_url = values.get("api_base_url", "")
    if api_base_url and not _secure_url(api_base_url):
        raise ProviderConfigError(
            "api urls must use https unless loopback",
            path=path,
            field="api_base_url",
        )
    for field in ("api_max_concurrency", "api_rate_per_min"):
        if values.get(field, 1) < 1:
            raise ProviderConfigError(
                "field must be at least 1", path=path, field=field
            )
    imap_port = values["imap_port"]
    smtp_port = values.get("smtp_port", 587)
    for field, port in (("imap_port", imap_port), ("smtp_port", smtp_port)):
        if not 1 <= port <= 65535:
            raise ProviderConfigError("port is out of range", path=path, field=field)
    spec = ProviderSpec(
        id=provider_id,
        label=values["label"],
        imap_host=values["imap_host"],
        imap_port=imap_port,
        imap_tls=imap_tls,
        smtp_host=values.get("smtp_host", ""),
        smtp_port=smtp_port,
        smtp_tls=smtp_tls,
        auth_kind=auth_kind,
        smtp_auth_mechanism=values.get("smtp_auth_mechanism", "PLAIN").upper(),
        sent_folder=values.get("sent_folder", "Sent"),
        supports_idle=values.get("supports_idle", True),
        requires_user_agent=values.get("requires_user_agent", False),
        attachment_max_bytes=values.get("attachment_max_bytes", 26214400),
        notes=values.get("notes", ""),
        oauth_authorize_url=values.get("oauth_authorize_url", ""),
        oauth_token_url=values.get("oauth_token_url", ""),
        oauth_scopes=scopes,
        oauth_client_id=values.get("oauth_client_id", ""),
        oauth_client_secret=values.get("oauth_client_secret", ""),
        oauth_tenant=values.get("oauth_tenant", "common"),
        oauth_extra_params=extra,
        transport=transport,
        api_base_url=api_base_url,
        api_max_concurrency=values.get("api_max_concurrency", 2),
        api_rate_per_min=values.get("api_rate_per_min", 120),
        api_scopes=api_scopes,
    )
    _check_oauth(spec, path)
    if spec.smtp_auth_mechanism not in {"XOAUTH2", "PLAIN"}:
        raise ProviderConfigError(
            "unknown SMTP mechanism", path=path, field="smtp_auth_mechanism"
        )
    if spec.imap_tls is TlsMode.NONE and not _loopback(spec.imap_host):
        raise ProviderConfigError(
            "plaintext IMAP is only allowed on loopback",
            path=path,
            field="imap_tls",
        )
    return spec


def _check_types(values: dict[str, Any], path: Path | None) -> None:
    for field in ("label", "imap_host"):
        if not isinstance(values[field], str):
            raise ProviderConfigError("field must be a string", path=path, field=field)
    for field in _INT_FIELDS:
        value = values.get(field)
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, int)
        ):
            raise ProviderConfigError(
                "field must be an integer", path=path, field=field
            )
    for field in _STRING_FIELDS:
        value = values.get(field)
        if value is not None and not isinstance(value, str):
            raise ProviderConfigError("field must be a string", path=path, field=field)
    for field in ("supports_idle", "requires_user_agent"):
        value = values.get(field)
        if value is not None and not isinstance(value, bool):
            raise ProviderConfigError("field must be a boolean", path=path, field=field)


def _tls(value: str, path: Path | None, field: str) -> TlsMode:
    try:
        return TlsMode(value)
    except ValueError as error:
        raise ProviderConfigError(
            "field has an unknown value", path=path, field=field
        ) from error


def _auth(value: str, path: Path | None) -> AuthKind:
    try:
        return AuthKind(value)
    except ValueError as error:
        raise ProviderConfigError(
            "field has an unknown value", path=path, field="auth_kind"
        ) from error


def _strings(value: Any, path: Path | None, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise ProviderConfigError(
            "field must be a list of strings", path=path, field=field
        )
    return tuple(value)


def _table(value: Any, path: Path | None) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, dict) or not all(
        isinstance(key, str) and isinstance(item, str) for key, item in value.items()
    ):
        raise ProviderConfigError(
            "field must be a table of strings",
            path=path,
            field="oauth_extra_params",
        )
    return tuple(sorted(value.items()))


def _check_oauth(spec: ProviderSpec, path: Path | None) -> None:
    if spec.auth_kind is not AuthKind.OAUTH2:
        return
    for field in ("oauth_authorize_url", "oauth_token_url"):
        value = getattr(spec, field)
        if not value:
            raise ProviderConfigError(
                "an oauth provider needs this field", path=path, field=field
            )
        if not _secure_url(value):
            raise ProviderConfigError(
                "oauth urls must use https unless loopback",
                path=path,
                field=field,
            )
    if not spec.oauth_scopes:
        raise ProviderConfigError(
            "an oauth provider needs scopes", path=path, field="oauth_scopes"
        )


def _loopback(host: str) -> bool:
    return host in {"localhost", "127.0.0.1", "::1"}


def _secure_url(value: str) -> bool:
    parsed = urlparse(value)
    if parsed.scheme == "https":
        return True
    return parsed.scheme == "http" and _loopback(parsed.hostname or "")
