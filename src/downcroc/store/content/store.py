from __future__ import annotations

import contextlib
import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from downcroc.domain.errors import ContentCorrupt, ContentMissing
from downcroc.runtime.fs import O_NOFOLLOW, restrict, restrict_fd, sync_dir

_UNSAFE = re.compile(r"[^A-Za-z0-9._ -]+")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


@dataclass(frozen=True)
class StoredContent:
    path: str
    hash: str
    size: int


def safe_filename(name: str, fallback: str) -> str:
    base = name.replace("\\", "/").rsplit("/", 1)[-1]
    base = _CONTROL.sub("_", base).strip().lstrip(".").strip()
    base = _UNSAFE.sub("_", base)
    if not base:
        base = fallback
    if len(base) > 120:
        stem, dot, suffix = base.rpartition(".")
        if dot and len(suffix) <= 12:
            base = f"{stem[: 119 - len(suffix)]}.{suffix}"
        else:
            base = base[:120]
    return base


class ContentStore:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)
        restrict(self._root, 0o700)

    def put_attachment(
        self,
        account_id: str,
        message_id: str,
        index: int,
        filename: str,
        payload: bytes,
    ) -> StoredContent:
        name = safe_filename(filename, f"attachment-{index}")
        relative = PurePosixPath(
            "attachments", account_id, message_id, f"{index}-{name}"
        )
        target = self._root / Path(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        restrict(target.parent, 0o700)
        self._write(target, payload)
        digest = hashlib.sha256(payload).hexdigest()
        return StoredContent(path=relative.as_posix(), hash=digest, size=len(payload))

    def put_batch_source(self, batch_id: str, payload: bytes) -> StoredContent:
        relative = PurePosixPath("batches", batch_id, "source.json")
        target = self._root / Path(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        restrict(target.parent, 0o700)
        self._write(target, payload)
        digest = hashlib.sha256(payload).hexdigest()
        return StoredContent(path=relative.as_posix(), hash=digest, size=len(payload))

    def put_job_message(self, job_id: str, payload: bytes) -> StoredContent:
        relative = PurePosixPath("jobs", job_id, "message.eml")
        target = self._root / Path(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        restrict(target.parent, 0o700)
        self._write(target, payload)
        digest = hashlib.sha256(payload).hexdigest()
        return StoredContent(path=relative.as_posix(), hash=digest, size=len(payload))

    def read_bytes(self, path: str) -> bytes:
        target = self.resolve(path)
        try:
            return target.read_bytes()
        except FileNotFoundError as error:
            raise ContentMissing(
                "the stored content is missing",
                hint="the file was removed outside downcroc",
            ) from error
        except OSError as error:
            raise ContentMissing("the stored content cannot be read") from error

    def discard(self, path: str) -> int:
        target = self.resolve(path)
        try:
            size = target.stat().st_size
        except FileNotFoundError:
            return 0
        try:
            target.unlink()
        except FileNotFoundError:
            return 0
        return int(size)

    def read(self, path: str, expected_hash: str) -> bytes:
        target = self.resolve(path)
        try:
            payload = target.read_bytes()
        except FileNotFoundError as error:
            raise ContentMissing(
                "the stored content is missing",
                hint="the file was removed outside downcroc",
            ) from error
        except OSError as error:
            raise ContentMissing("the stored content cannot be read") from error
        if hashlib.sha256(payload).hexdigest() != expected_hash:
            raise ContentCorrupt(
                "the stored content does not match its recorded hash",
                hint="restore the file from a backup",
            )
        return payload

    def resolve(self, path: str) -> Path:
        relative = PurePosixPath(path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ContentMissing("the content path is not valid")
        target = (self._root / Path(*relative.parts)).resolve()
        if not target.is_relative_to(self._root.resolve()):
            raise ContentMissing("the content path escapes the store")
        return target

    @staticmethod
    def _write(target: Path, payload: bytes) -> None:
        temporary = target.with_name(f"{target.name}.tmp")
        try:
            descriptor = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_TRUNC | O_NOFOLLOW,
                0o600,
            )
            with os.fdopen(descriptor, "wb") as handle:
                restrict_fd(handle.fileno(), 0o600)
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
            sync_dir(target.parent)
        finally:
            with contextlib.suppress(FileNotFoundError):
                temporary.unlink()
