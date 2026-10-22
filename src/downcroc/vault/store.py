from __future__ import annotations

import contextlib
import os
from pathlib import Path


class StoreError(Exception):
    pass


def read(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as error:
        raise StoreError(str(error)) from error


def write_atomic(path: Path, payload: bytes) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW,
            0o600,
        )
        with os.fdopen(descriptor, "wb") as handle:
            os.fchmod(handle.fileno(), 0o600)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except OSError as error:
        raise StoreError(str(error)) from error
    finally:
        with contextlib.suppress(FileNotFoundError):
            temporary.unlink()
