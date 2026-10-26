from __future__ import annotations

import os
import shutil
import tempfile
import time
from pathlib import Path

O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


def restrict(path: Path, mode: int) -> None:
    if os.name == "nt":
        return
    path.chmod(mode)


def restrict_fd(descriptor: int, mode: int) -> None:
    if os.name == "nt" or not hasattr(os, "fchmod"):
        return
    os.fchmod(descriptor, mode)


def sync_dir(path: Path) -> None:
    if os.name == "nt":
        return
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def replace(source: Path, target: Path, timeout: float = 10.0) -> None:
    if os.name != "nt":
        os.replace(source, target)
        return
    deadline = time.monotonic() + timeout
    while True:
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.05)


def remove_tree(path: Path, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while True:
        try:
            shutil.rmtree(path)
            return
        except FileNotFoundError:
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.05)


def atomic_write(path: Path, payload: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}-",
        suffix=".tmp",
    )
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        restrict(Path(temporary), mode)
        os.replace(temporary, path)
        sync_dir(path.parent)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
