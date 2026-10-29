from __future__ import annotations

import os
import tomllib
from importlib.resources import files
from pathlib import Path
from typing import Any

from downcroc.domain.errors import ProviderConfigError, ProviderUnknown
from downcroc.domain.providers import AuthKind, ProviderSpec
from downcroc.providers import declaration, writer
from downcroc.providers.declaration import REQUIRED
from downcroc.runtime.logging.setup import EventLogger

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
        "transport",
        "api_base_url",
        "api_max_concurrency",
        "api_rate_per_min",
        "api_scopes",
    }
)
FIELDS = REQUIRED | OPTIONAL
MODE = 0o600


class ProviderRegistry:
    def __init__(
        self,
        specs: dict[str, ProviderSpec],
        config_dir: Path | None = None,
        sources: dict[str, Path] | None = None,
        log: EventLogger | None = None,
    ) -> None:
        self._specs = specs
        self._config_dir = config_dir
        self._sources = sources or {}
        self._log = log

    def reload(self) -> None:
        if self._config_dir is None or self._log is None:
            return
        fresh = type(self).load(self._config_dir, self._log)
        self._specs = fresh._specs
        self._sources = fresh._sources

    @property
    def config_file(self) -> Path:
        root = self._config_dir or Path()
        return root / "providers.toml"

    def source_of(self, provider_id: str) -> Path | None:
        return self._sources.get(provider_id)

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
        return cls(specs, config_dir, sources, log)

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

    def readiness(self, spec: ProviderSpec) -> tuple[bool, list[str]]:
        return readiness(spec)

    def save(self, provider_id: str, values: dict[str, Any]) -> ProviderSpec:
        current = writer.read(self.config_file)
        merged = dict(current.get(provider_id, {}))
        merged.update({key: item for key, item in values.items() if item is not None})
        merged.pop("id", None)
        current[provider_id] = merged
        self._rewrite(current)
        return self.get(provider_id)

    def remove(self, provider_id: str) -> bool:
        current = writer.read(self.config_file)
        if provider_id not in current:
            return False
        del current[provider_id]
        self._rewrite(current)
        return True

    def _rewrite(self, providers: dict[str, dict[str, Any]]) -> None:
        previous = (
            self.config_file.read_text(encoding="utf-8")
            if self.config_file.is_file()
            else None
        )
        writer.write(self.config_file, providers)
        try:
            self.reload()
        except ProviderConfigError:
            if previous is None:
                self.config_file.unlink(missing_ok=True)
            else:
                self.config_file.write_text(previous, encoding="utf-8")
            self.reload()
            raise

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
        return declaration.parse_spec(provider_id, values, path)

    @classmethod
    def _secure(cls, path: Path, log: EventLogger) -> None:
        if os.name == "nt":
            return
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


def readiness(spec: ProviderSpec) -> tuple[bool, list[str]]:
    missing: list[str] = []
    if not spec.imap_host:
        missing.append("imap_host")
    if not spec.smtp_host:
        missing.append("smtp_host")
    if spec.auth_kind is AuthKind.OAUTH2:
        if not spec.oauth_client_id:
            missing.append("oauth_client_id")
        if not spec.oauth_client_secret:
            missing.append("oauth_client_secret")
        if spec.oauth_tenant == "" and "microsoft" in spec.id:
            missing.append("oauth_tenant")
    return (not missing, missing)
