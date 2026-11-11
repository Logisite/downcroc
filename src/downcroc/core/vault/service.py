from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from sqlalchemy.exc import SQLAlchemyError

from downcroc.core.events import EventBus
from downcroc.core.vault.file import VaultFile
from downcroc.domain.errors import (
    VaultBadPassword,
    VaultExists,
    VaultLocked,
    VaultSecretMissing,
    VaultThrottled,
)
from downcroc.domain.secrets import KINDS
from downcroc.runtime.clock import utc_now
from downcroc.runtime.config.schema import VaultSettings
from downcroc.runtime.logging.setup import EventLogger
from downcroc.vault import format as vault_format
from downcroc.vault import secrets


@dataclass(frozen=True)
class VaultStatus:
    state: Literal["locked", "unlocked"]
    path: str
    unlocked_at: str | None
    attempts_left: int
    retry_after_s: float


class VaultService:
    def __init__(
        self,
        path: Path,
        settings: VaultSettings,
        bus: EventBus | None,
        log: EventLogger,
    ) -> None:
        self._path = path
        self._settings = settings
        self._bus = bus
        self._log = log
        self._lock = threading.RLock()
        self._key: bytearray | None = None
        self._header: vault_format.Header | None = None
        self._secrets: dict[str, dict[str, object]] | None = None
        self._unlocked_at: str | None = None
        self._failures = 0
        self._next_attempt = 0.0
        self._file = VaultFile(path, settings, log)
        self._file.fix_permissions()

    def status(self) -> VaultStatus:
        with self._lock:
            remaining = self._next_attempt - time.monotonic()
            return VaultStatus(
                state="unlocked" if self._key is not None else "locked",
                path=str(self._path),
                unlocked_at=self._unlocked_at,
                attempts_left=max(0, self._settings.free_attempts - self._failures),
                retry_after_s=max(0.0, round(remaining, 1)),
            )

    def exists(self) -> bool:
        return self._path.exists()

    def initialize(self, password: str) -> VaultStatus:
        with self._lock:
            if self._path.exists():
                raise VaultExists(
                    "a vault already exists",
                    hint="run downcroc vault unlock instead",
                )
            started = time.monotonic()
            header, key, payload = self._file.create(password)
            self._install(header, key, payload)
            self._failures = 0
            self._next_attempt = 0.0
            self._unlocked_at = utc_now()
            duration = round((time.monotonic() - started) * 1000)
            self._log.info("vault.created", duration_ms=duration)
            self._publish("vault.created", {"state": "unlocked"})
            return self.status()

    def unlock(self, password: str) -> VaultStatus:
        with self._lock:
            if self._key is not None:
                return self.status()
            remaining = self._next_attempt - time.monotonic()
            if remaining > 0:
                seconds = max(0.1, round(remaining, 1))
                raise VaultThrottled(
                    f"too many failed attempts, try again in {seconds} seconds",
                    hint=f"retry after {seconds} seconds",
                    details=[{"retry_after_s": seconds}],
                )
            started = time.monotonic()
            if not self._path.exists():
                raise VaultLocked(
                    "the vault does not exist",
                    hint="run downcroc vault init first",
                )
            try:
                header, key, payload = self._file.open(password)
            except VaultBadPassword:
                self._record_failure()
                raise
            self._install(header, key, payload)
            self._failures = 0
            self._next_attempt = 0.0
            self._unlocked_at = utc_now()
            duration = round((time.monotonic() - started) * 1000)
            self._log.info("vault.unlocked", duration_ms=duration)
            self._publish("vault.unlocked", {"state": "unlocked"})
            return self.status()

    def lock(self, reason: str) -> VaultStatus:
        with self._lock:
            if self._key is None:
                return self.status()
            self._key[:] = b"\0" * len(self._key)
            self._key = None
            self._header = None
            self._secrets = None
            self._unlocked_at = None
            self._log.info("vault.locked", reason=reason)
            self._publish("vault.locked", {"reason": reason})
            return self.status()

    def get_secret(self, key: str) -> secrets.Secret:
        with self._lock:
            payload = self._require_payload()
            record = payload.get(key)
            if record is None:
                raise VaultSecretMissing(f"no secret named {key}")
            return secrets.unpack(record)

    def ensure_unlocked(self) -> None:
        with self._lock:
            self._require_payload()

    def has_secret(self, key: str) -> bool:
        with self._lock:
            return key in self._require_payload()

    def keys(self) -> list[str]:
        with self._lock:
            return sorted(self._require_payload())

    def set_secret(
        self,
        key: str,
        value: str,
        *,
        expires_at: str | None = None,
        scopes: tuple[str, ...] = (),
    ) -> None:
        self.set_secrets({key: (value, expires_at, scopes)})

    def set_secrets(
        self,
        records: dict[str, tuple[str, str | None, tuple[str, ...]]],
    ) -> None:
        with self._lock:
            payload = dict(self._require_payload())
            for key, (value, expires_at, scopes) in records.items():
                secret = secrets.Secret(
                    value=value, expires_at=expires_at, scopes=scopes
                )
                payload[key] = secrets.pack(secret)
            self._write(payload)

    def delete_account_secrets(self, account_id: str) -> int:
        with self._lock:
            payload = self._require_payload()
            stale = {key for key in payload if _belongs_to_account(key, account_id)}
            return self.delete_secrets(stale)

    def delete_secrets(self, keys: set[str]) -> int:
        with self._lock:
            payload = self._require_payload()
            stale = {key for key in keys if key in payload}
            if not stale:
                return 0
            remaining = {
                key: value for key, value in payload.items() if key not in stale
            }
            self._write(remaining)
            return len(stale)

    def delete_secret(self, key: str) -> bool:
        return self.delete_secrets({key}) > 0

    def _install(
        self,
        header: vault_format.Header,
        key: bytes,
        payload: dict[str, dict[str, object]],
    ) -> None:
        self._key = bytearray(key)
        self._header = header
        self._secrets = payload

    def _require_payload(self) -> dict[str, dict[str, object]]:
        if self._key is None or self._header is None or self._secrets is None:
            raise VaultLocked("the vault is locked", hint="unlock the vault first")
        return self._secrets

    def _write(self, payload: dict[str, dict[str, object]]) -> None:
        header = self._header
        key = self._key
        if header is None or key is None:
            raise VaultLocked("the vault is locked", hint="unlock the vault first")
        self._header = self._file.write(header, bytes(key), payload)
        self._secrets = payload

    def _record_failure(self) -> None:
        self._failures += 1
        attempts_left = max(0, self._settings.free_attempts - self._failures)
        if self._failures >= self._settings.free_attempts:
            over = min(self._failures - self._settings.free_attempts, 32)
            delay = min(
                self._settings.base_delay_s * (2**over),
                self._settings.max_delay_s,
            )
            self._next_attempt = time.monotonic() + delay
        self._log.warning("vault.unlock_failed", attempts_left=attempts_left)

    def _publish(self, event: str, data: dict[str, object]) -> None:
        if self._bus is None:
            return
        try:
            self._bus.publish(event, data)
        except SQLAlchemyError as error:
            self._log.error(
                "event.publish_failed",
                event=event,
                reason=str(error),
            )


def _belongs_to_account(key: str, account_id: str) -> bool:
    owner, separator, kind = key.partition(":")
    return bool(separator) and owner == account_id and kind in KINDS
