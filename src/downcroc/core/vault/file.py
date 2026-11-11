from __future__ import annotations

import os
import time
from dataclasses import replace
from pathlib import Path

from downcroc.domain.errors import (
    VaultBadPassword,
    VaultCorrupt,
    VaultUnavailable,
    VaultWriteFailed,
)
from downcroc.runtime.config.schema import VaultSettings
from downcroc.runtime.logging.setup import EventLogger
from downcroc.vault import cipher, kdf, secrets, store
from downcroc.vault import format as vault_format

MODE = 0o600


class VaultFile:
    def __init__(self, path: Path, settings: VaultSettings, log: EventLogger) -> None:
        self._path = path
        self._settings = settings
        self._log = log

    def create(
        self, password: str
    ) -> tuple[vault_format.Header, bytes, dict[str, dict[str, object]]]:
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
        self._log.info(
            "vault.created",
            path=str(self._path),
            memory_kib=params.memory_kib,
            iterations=params.iterations,
            lanes=params.lanes,
            duration_ms=duration,
        )
        return header, key, payload

    def open(
        self, password: str
    ) -> tuple[vault_format.Header, bytes, dict[str, dict[str, object]]]:
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
        return header, key, payload

    def write(
        self,
        header: vault_format.Header,
        key: bytes,
        payload: dict[str, dict[str, object]],
    ) -> vault_format.Header:
        started = time.monotonic()
        candidate = replace(header, nonce=os.urandom(vault_format.NONCE_BYTES))
        try:
            ciphertext = cipher.seal(
                key,
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
        self._log.info(
            "vault.saved",
            bytes=len(data),
            duration_ms=duration,
            state="unlocked",
        )
        return candidate

    def fix_permissions(self) -> None:
        if os.name == "nt":
            return
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
