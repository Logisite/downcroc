from __future__ import annotations

import asyncio
import hashlib
import logging
import threading
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from downcroc.core.accounts_service import AccountsService
from downcroc.core.followups import FollowUpService
from downcroc.domain.accounts import SendPolicy
from downcroc.domain.errors import ConfigRejected
from downcroc.runtime.config.loader import ConfigError, read, write
from downcroc.runtime.config.schema import SendingSettings, Settings
from downcroc.runtime.config.spec import changed_paths, describe, merge
from downcroc.runtime.logging.setup import EventLogger
from downcroc.runtime.paths import Paths


@dataclass(frozen=True)
class ConfigApply:
    changed: list[str]


def _policy(settings: SendingSettings) -> SendPolicy:
    return SendPolicy(
        daily_allowance=settings.daily_allowance,
        window_start=settings.window_start,
        window_end=settings.window_end,
        jitter_min=settings.jitter_min,
        jitter_max=settings.jitter_max,
        max_in_flight=settings.max_in_flight,
        enabled=settings.enabled,
    )


def _assign(target: BaseModel, source: BaseModel) -> None:
    for name in type(target).model_fields:
        value = getattr(source, name)
        current = getattr(target, name)
        if isinstance(current, BaseModel) and isinstance(value, BaseModel):
            _assign(current, value)
        else:
            setattr(target, name, value)


def _validation_error(error: ValidationError) -> tuple[str, str]:
    first = error.errors()[0]
    field = ".".join(str(part) for part in first["loc"]) or "config.toml"
    return field, str(first["msg"])


class ConfigService:
    def __init__(
        self,
        paths: Paths,
        settings: Settings,
        log: EventLogger,
        accounts: AccountsService,
        followups: FollowUpService,
    ) -> None:
        self._paths = paths
        self._settings = settings
        self._log = log
        self._accounts = accounts
        self._followups = followups
        self._lock = threading.RLock()
        self._digest: str | None = None
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            document: dict[str, Any] | None = None
            error: str | None = None
            try:
                text = self._paths.config_file.read_text(encoding="utf-8")
                document = tomllib.loads(text)
            except OSError as problem:
                error = problem.strerror or str(problem)
            except tomllib.TOMLDecodeError as problem:
                error = f"invalid TOML: {problem}"
            return {
                "config": self._settings.model_dump(mode="json"),
                "document": document,
                "path": str(self._paths.config_file),
                "error": error,
            }

    def fields(self) -> list[dict[str, Any]]:
        return describe()

    def patch(self, patch: dict[str, Any]) -> ConfigApply:
        with self._lock:
            if not patch:
                return ConfigApply(changed=[])
            base = self._on_disk()
            current = self._settings.model_dump(mode="json")
            merged = merge(base.model_dump(mode="json"), patch)
            try:
                candidate = Settings.model_validate(merged)
            except ValidationError as error:
                field, reason = _validation_error(error)
                raise self._reject(field, reason) from error
            changed = changed_paths(current, candidate.model_dump(mode="json"))
            try:
                write(self._paths.config_file, candidate)
            except OSError as problem:
                reason = problem.strerror or str(problem)
                raise self._reject("config.toml", reason) from problem
            self._apply(candidate)
            self._digest = self._file_digest()
            if changed:
                self._log.info("config.reloaded", changed=changed)
            return ConfigApply(changed=changed)

    def reload_if_changed(self) -> ConfigApply | None:
        with self._lock:
            digest = self._file_digest()
            if digest == self._digest:
                return None
            if digest is None:
                self._digest = None
                self._log.warning(
                    "config.rejected",
                    field="config.toml",
                    reason="the config file is missing",
                )
                return None
            try:
                candidate = read(self._paths.config_file)
            except ConfigError as error:
                self._digest = digest
                self._log.warning(
                    "config.rejected",
                    field=error.field or "config.toml",
                    reason=str(error),
                )
                return None
            current = self._settings.model_dump(mode="json")
            changed = changed_paths(current, candidate.model_dump(mode="json"))
            if not changed:
                self._digest = digest
                return None
            self._apply(candidate)
            self._digest = digest
            self._log.info("config.reloaded", changed=changed)
            return ConfigApply(changed=changed)

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="config-watcher")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            await self._task
            self._task = None

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                await asyncio.to_thread(self.reload_if_changed)
            except Exception as error:  # noqa: BLE001
                self._log.error(
                    "config.reload_failed",
                    error=type(error).__name__,
                )
            try:
                await asyncio.wait_for(
                    self._stop.wait(),
                    timeout=self._settings.config.reload_check_s,
                )
            except TimeoutError:
                continue

    def _on_disk(self) -> Settings:
        if not self._paths.config_file.exists():
            return self._settings
        try:
            return read(self._paths.config_file)
        except ConfigError as error:
            raise self._reject(
                error.field or "config.toml",
                str(error),
            ) from error

    def _apply(self, candidate: Settings) -> None:
        old_sending = _policy(self._settings.sending)
        new_sending = _policy(candidate.sending)
        old_level = self._settings.logging.level
        if old_sending != new_sending:
            self._accounts.apply_sending_defaults(old_sending, new_sending)
        _assign(self._settings, candidate)
        self._followups.reload_limits()
        if old_level != candidate.logging.level:
            level = getattr(logging, candidate.logging.level.upper())
            logging.getLogger().setLevel(level)

    def _reject(self, field: str, reason: str) -> ConfigRejected:
        self._log.warning("config.rejected", field=field, reason=reason)
        return ConfigRejected(
            "the config is not valid",
            hint="fix the field and try again",
            fields={"field": field, "reason": reason},
        )

    def _file_digest(self) -> str | None:
        try:
            data = Path(self._paths.config_file).read_bytes()
        except OSError:
            return None
        return hashlib.sha256(data).hexdigest()
