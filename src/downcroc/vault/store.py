from __future__ import annotations

import contextlib
import os
from pathlib import Path

from downcroc.runtime.fs import O_NOFOLLOW, restrict_fd, sync_dir


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
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC | O_NOFOLLOW,
            0o600,
        )
        with os.fdopen(descriptor, "wb") as handle:
            restrict_fd(handle.fileno(), 0o600)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        sync_dir(path.parent)
    except OSError as error:
        raise StoreError(str(error)) from error
    finally:
        with contextlib.suppress(FileNotFoundError):
            temporary.unlink()
