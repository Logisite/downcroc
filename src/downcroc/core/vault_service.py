from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

from sqlalchemy.exc import SQLAlchemyError

from downcroc.core.events import EventBus
from downcroc.domain.errors import (
    VaultAlreadyUnlocked,
    VaultBadPassword,
    VaultCorrupt,
    VaultLocked,
    VaultSecretMissing,
    VaultThrottled,
    VaultUnavailable,
    VaultWriteFailed,
)
from downcroc.domain.secrets import KINDS
from downcroc.runtime.clock import utc_now
from downcroc.runtime.config.schema import VaultSettings
from downcroc.runtime.logging.setup import EventLogger
from downcroc.vault import cipher, kdf, secrets, store
from downcroc.vault import format as vault_format

MODE = 0o600


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
        self._fix_permissions()

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

    def unlock(self, password: str) -> VaultStatus:
        with self._lock:
            if self._key is not None:
                raise VaultAlreadyUnlocked(
                    "the vault is already unlocked",
                    hint="lock the vault first",
                )
            remaining = self._next_attempt - time.monotonic()
            if remaining > 0:
                seconds = max(0.1, round(remaining, 1))
                raise VaultThrottled(
                    f"too many failed attempts, try again in {seconds} seconds",
                    hint=f"retry after {seconds} seconds",
                )
            started = time.monotonic()
            if self._path.exists():
                self._open(password)
            else:
                self._create(password)
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
            stale = []
            for key in payload:
                owner, separator, kind = key.partition(":")
                if separator and owner == account_id and kind in KINDS:
                    stale.append(key)
            if not stale:
                return 0
            remaining = {
                key: value for key, value in payload.items() if key not in stale
            }
            self._write(remaining)
            return len(stale)

    def prune_account_secrets(self, known_ids: set[str]) -> int:
        with self._lock:
            payload = self._require_payload()
            stale = []
            for key in payload:
                account_id, separator, kind = key.partition(":")
                if separator and kind in KINDS and account_id not in known_ids:
                    stale.append(key)
            if not stale:
                return 0
            remaining = {
                key: value for key, value in payload.items() if key not in stale
            }
            self._write(remaining)
            return len(stale)

    def delete_secret(self, key: str) -> bool:
        with self._lock:
            payload = self._require_payload()
            if key not in payload:
                return False
            remaining = {
                name: record for name, record in payload.items() if name != key
            }
            self._write(remaining)
            return True

    def _create(self, password: str) -> None:
        salt = os.urandom(vault_format.SALT_BYTES)
        try:
            params, key, duration = kdf.tune(
                password,
                salt,
                kdf.KdfParams(
                    memory_kib=self._settings.kdf_memory_kib,
                    iterations=self._settings.kdf_iterations,
                    lanes=self._settings.kdf_lanes,
                ),
                self._settings.kdf_target_ms,
                self._settings.kdf_max_memory_kib,
            )
        except kdf.KdfError as error:
            self._log.error("vault.derive_failed", reason=str(error))
            raise VaultUnavailable(
                "the vault key cannot be derived on this machine",
                hint="lower vault.kdf_memory_kib in the config",
            ) from error
        header = vault_format.Header(
            memory_kib=params.memory_kib,
            iterations=params.iterations,
            lanes=params.lanes,
            salt=salt,
            nonce=os.urandom(vault_format.NONCE_BYTES),
        )
        payload: dict[str, dict[str, object]] = {}
        ciphertext = cipher.seal(
            key,
            vault_format.header_bytes(header),
            header.nonce,
            secrets.encode_map(payload),
        )
        data = vault_format.encode(header, ciphertext)
        try:
            store.write_atomic(self._path, data)
        except store.StoreError as error:
            self._log.error("vault.write_failed", reason=str(error))
            raise VaultWriteFailed(
                "the vault could not be written",
                hint="check free disk space and directory permissions",
            ) from error
        self._install(header, key, payload)
        self._log.info(
            "vault.created",
            path=str(self._path),
            memory_kib=params.memory_kib,
            iterations=params.iterations,
            lanes=params.lanes,
            duration_ms=duration,
        )

    def _open(self, password: str) -> None:
        try:
            data = store.read(self._path)
            header, ciphertext = vault_format.decode(data)
        except vault_format.FileCorrupt as error:
            self._log.error(
                "vault.corrupt", offset=error.offset, expected=error.expected
            )
            raise VaultCorrupt(
                "the vault file is damaged",
                hint="restore vault.enc from a backup",
            ) from error
        except store.StoreError as error:
            self._log.error("vault.read_failed", reason=str(error))
            raise VaultUnavailable(
                "the vault file cannot be read",
                hint="check its permissions and the data directory",
            ) from error

        try:
            key = kdf.derive(
                password,
                header.salt,
                kdf.KdfParams(
                    memory_kib=header.memory_kib,
                    iterations=header.iterations,
                    lanes=header.lanes,
                ),
            )
        except kdf.KdfError as error:
            self._log.error("vault.derive_failed", reason=str(error))
            raise VaultUnavailable(
                "the vault key cannot be derived on this machine",
                hint="restore a backup created with supported parameters",
            ) from error

        try:
            plaintext = cipher.unseal(
                key,
                vault_format.header_bytes(header),
                header.nonce,
                ciphertext,
            )
            payload = secrets.decode_map(plaintext)
        except cipher.DecryptError as error:
            self._record_failure()
            raise VaultBadPassword("the master password is not correct") from error
        except secrets.PayloadError as error:
            self._log.error(
                "vault.corrupt",
                offset=vault_format.FIXED_BYTES,
                expected="a cbor map",
            )
            raise VaultCorrupt(
                "the vault file is damaged",
                hint="restore vault.enc from a backup",
            ) from error
        self._install(header, key, payload)

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
        started = time.monotonic()
        candidate = replace(header, nonce=os.urandom(vault_format.NONCE_BYTES))
        try:
            ciphertext = cipher.seal(
                bytes(key),
                vault_format.header_bytes(candidate),
                candidate.nonce,
                secrets.encode_map(payload),
            )
            data = vault_format.encode(candidate, ciphertext)
            store.write_atomic(self._path, data)
        except store.StoreError as error:
            self._log.error("vault.write_failed", reason=str(error))
            raise VaultWriteFailed(
                "the vault could not be written",
                hint="check free disk space and directory permissions",
            ) from error
        duration = round((time.monotonic() - started) * 1000)
        self._header = candidate
        self._secrets = payload
        self._log.info("vault.sealed", bytes=len(data), duration_ms=duration)

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

    def _fix_permissions(self) -> None:
        try:
            mode = self._path.stat().st_mode & 0o777
        except FileNotFoundError:
            return
        except OSError as error:
            self._log.warning(
                "vault.permissions",
                path=str(self._path),
                reason=str(error),
            )
            return
        if mode & 0o077 == 0:
            return
        try:
            self._path.chmod(MODE)
        except OSError as error:
            self._log.warning(
                "vault.permissions",
                path=str(self._path),
                mode=oct(mode),
                fixed=False,
                reason=str(error),
            )
            return
        self._log.warning(
            "vault.permissions",
            path=str(self._path),
            mode=oct(mode),
            fixed=True,
        )

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
