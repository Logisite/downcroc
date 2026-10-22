from __future__ import annotations

import tomllib
from importlib.resources import files
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from downcroc.domain.errors import ProviderConfigError, ProviderUnknown
from downcroc.domain.providers import AuthKind, ProviderSpec, TlsMode
from downcroc.runtime.logging.setup import EventLogger

REQUIRED = frozenset({"id", "label", "imap_host", "imap_port", "imap_tls", "auth_kind"})
OPTIONAL = frozenset(
    {
        "smtp_host",
        "smtp_port",
        "smtp_tls",
        "smtp_auth_mechanism",
        "sent_folder",
        "supports_idle",
        "requires_user_agent",
        "attachment_max_bytes",
        "notes",
        "oauth_authorize_url",
        "oauth_token_url",
        "oauth_scopes",
        "oauth_client_id",
        "oauth_client_secret",
        "oauth_tenant",
        "oauth_extra_params",
    }
)
FIELDS = REQUIRED | OPTIONAL
MODE = 0o600


class ProviderRegistry:
    def __init__(self, specs: dict[str, ProviderSpec]) -> None:
        self._specs = specs

    @classmethod
    def load(cls, config_dir: Path, log: EventLogger) -> ProviderRegistry:
        raw: dict[str, dict[str, Any]] = {}
        sources: dict[str, Path] = {}
        try:
            for path in sorted(files("downcroc.providers.declarations").iterdir()):
                if path.name.endswith(".toml"):
                    cls._merge(raw, sources, cls._read(path), path, None)
            combined = config_dir / "providers.toml"
            if combined.is_file():
                cls._secure(combined, log)
                cls._merge_combined(raw, sources, combined)
            dropped = config_dir / "providers.d"
            if dropped.is_dir():
                for path in sorted(dropped.glob("*.toml")):
                    cls._secure(path, log)
                    cls._merge(raw, sources, cls._read(path), path, None)
            specs = {
                provider_id: cls._spec(provider_id, values, sources.get(provider_id))
                for provider_id, values in raw.items()
            }
        except ProviderConfigError as error:
            log.error(
                "provider.registry_failed",
                path=str(error.path) if error.path else None,
                field=error.field,
                reason=error.message,
            )
            raise
        log.info(
            "provider.registry",
            declarations=sorted(specs),
            count=len(specs),
        )
        return cls(specs)

    def get(self, provider_id: str) -> ProviderSpec:
        spec = self._specs.get(provider_id)
        if spec is None:
            raise ProviderUnknown(
                f"provider {provider_id} is not declared",
                hint="add it to providers.toml or providers.d",
            )
        return spec

    def has(self, provider_id: str) -> bool:
        return provider_id in self._specs

    def list(self) -> list[ProviderSpec]:
        return [self._specs[key] for key in sorted(self._specs)]

    @classmethod
    def _read(cls, path: Any) -> dict[str, Any]:
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except OSError as error:
            raise ProviderConfigError(
                "the declaration cannot be read", path=Path(str(path))
            ) from error
        except tomllib.TOMLDecodeError as error:
            raise ProviderConfigError(
                f"invalid TOML at line {error.lineno}",
                path=Path(str(path)),
                field="toml",
            ) from error
        if not isinstance(data, dict):
            raise ProviderConfigError("the declaration is not a table", path=path)
        return data

    @classmethod
    def _merge_combined(
        cls,
        raw: dict[str, dict[str, Any]],
        sources: dict[str, Path],
        path: Path,
    ) -> None:
        data = cls._read(path)
        unknown = set(data) - {"providers"}
        if unknown:
            raise ProviderConfigError(
                "unknown top level key", path=path, field=min(unknown)
            )
        tables = data.get("providers", {})
        if not isinstance(tables, dict):
            raise ProviderConfigError(
                "providers must be a table", path=path, field="providers"
            )
        for provider_id, values in tables.items():
            if not isinstance(values, dict):
                raise ProviderConfigError(
                    "a provider entry must be a table",
                    path=path,
                    field=provider_id,
                )
            cls._merge(raw, sources, values, path, provider_id)

    @classmethod
    def _merge(
        cls,
        raw: dict[str, dict[str, Any]],
        sources: dict[str, Path],
        values: dict[str, Any],
        path: Any,
        forced_id: str | None,
    ) -> None:
        provider_id = forced_id or values.get("id")
        if not isinstance(provider_id, str) or not provider_id:
            raise ProviderConfigError(
                "a declaration needs a string id", path=Path(str(path)), field="id"
            )
        unknown = set(values) - FIELDS
        if unknown:
            raise ProviderConfigError(
                "unknown provider field",
                path=Path(str(path)),
                field=min(unknown),
            )
        base = raw.get(provider_id, {})
        merged = {**base, **values}
        merged["id"] = provider_id
        raw[provider_id] = merged
        sources[provider_id] = Path(str(path))

    @classmethod
    def _spec(
        cls, provider_id: str, values: dict[str, Any], path: Path | None
    ) -> ProviderSpec:
        missing = sorted(REQUIRED - set(values))
        if missing:
            raise ProviderConfigError(
                "a declaration is incomplete", path=path, field=missing[0]
            )
        for field in ("label", "imap_host"):
            if not isinstance(values[field], str):
                raise ProviderConfigError(
                    "field must be a string", path=path, field=field
                )
        for field in ("imap_port", "smtp_port", "attachment_max_bytes"):
            value = values.get(field)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int)
            ):
                raise ProviderConfigError(
                    "field must be an integer", path=path, field=field
                )
        for field in (
            "smtp_host",
            "smtp_auth_mechanism",
            "sent_folder",
            "notes",
            "oauth_authorize_url",
            "oauth_token_url",
            "oauth_client_id",
            "oauth_client_secret",
            "oauth_tenant",
        ):
            value = values.get(field)
            if value is not None and not isinstance(value, str):
                raise ProviderConfigError(
                    "field must be a string", path=path, field=field
                )
        for field in ("supports_idle", "requires_user_agent"):
            value = values.get(field)
            if value is not None and not isinstance(value, bool):
                raise ProviderConfigError(
                    "field must be a boolean", path=path, field=field
                )
        try:
            imap_tls = TlsMode(values["imap_tls"])
        except ValueError as error:
            raise ProviderConfigError(
                "field has an unknown value", path=path, field="imap_tls"
            ) from error
        try:
            smtp_tls = TlsMode(values.get("smtp_tls", "starttls"))
        except ValueError as error:
            raise ProviderConfigError(
                "field has an unknown value", path=path, field="smtp_tls"
            ) from error
        try:
            auth_kind = AuthKind(values["auth_kind"])
        except ValueError as error:
            raise ProviderConfigError(
                "field has an unknown value", path=path, field="auth_kind"
            ) from error
        scopes = values.get("oauth_scopes", [])
        if not isinstance(scopes, list) or not all(
            isinstance(item, str) and item for item in scopes
        ):
            raise ProviderConfigError(
                "field must be a list of strings", path=path, field="oauth_scopes"
            )
        extra = values.get("oauth_extra_params", {})
        if not isinstance(extra, dict) or not all(
            isinstance(key, str) and isinstance(item, str)
            for key, item in extra.items()
        ):
            raise ProviderConfigError(
                "field must be a table of strings",
                path=path,
                field="oauth_extra_params",
            )
        imap_port = values["imap_port"]
        smtp_port = values.get("smtp_port", 587)
        for field, port in (("imap_port", imap_port), ("smtp_port", smtp_port)):
            if not 1 <= port <= 65535:
                raise ProviderConfigError(
                    "port is out of range", path=path, field=field
                )
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
            oauth_scopes=tuple(scopes),
            oauth_client_id=values.get("oauth_client_id", ""),
            oauth_client_secret=values.get("oauth_client_secret", ""),
            oauth_tenant=values.get("oauth_tenant", "common"),
            oauth_extra_params=tuple(sorted(extra.items())),
        )
        if spec.auth_kind is AuthKind.OAUTH2:
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

    @classmethod
    def _secure(cls, path: Path, log: EventLogger) -> None:
        try:
            mode = path.stat().st_mode & 0o777
        except OSError as error:
            log.warning("provider.permissions", path=str(path), reason=str(error))
            return
        if mode & 0o077 == 0:
            return
        try:
            path.chmod(MODE)
        except OSError as error:
            log.warning(
                "provider.permissions",
                path=str(path),
                mode=oct(mode),
                fixed=False,
                reason=str(error),
            )
            return
        log.warning(
            "provider.permissions",
            path=str(path),
            mode=oct(mode),
            fixed=True,
        )


def _loopback(host: str) -> bool:
    return host in {"127.0.0.1", "::1", "localhost"}


def _secure_url(value: str) -> bool:
    parsed = urlparse(value)
    if not parsed.hostname:
        return False
    if parsed.scheme == "https":
        return True
    return parsed.scheme == "http" and _loopback(parsed.hostname)
