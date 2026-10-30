from __future__ import annotations

import os
from pathlib import Path
from typing import IO

from downcroc.runtime.service.process import is_alive
from downcroc.runtime.service.registry import ServiceInfo, read

if os.name == "nt":
    import msvcrt
else:
    import fcntl


class AlreadyRunning(RuntimeError):
    def __init__(self, info: ServiceInfo | None) -> None:
        self.info = info
        if info is None:
            super().__init__("another downcroc daemon holds the lock")
        else:
            super().__init__(f"downcroc is already running on pid {info.pid}")


class InstanceLock:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._handle: IO[bytes] | None = None

    def acquire(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        handle = self._path.open("a+b")
        try:
            self._lock(handle)
        except OSError:
            handle.close()
            raise AlreadyRunning(None) from None
        handle.seek(0)
        handle.truncate()
        handle.write(str(os.getpid()).encode("ascii"))
        handle.flush()
        self._handle = handle

    def release(self) -> None:
        if self._handle is None:
            return
        try:
            self._unlock(self._handle)
        finally:
            self._handle.close()
            self._handle = None

    @staticmethod
    def _lock(handle: IO[bytes]) -> None:
        if os.name == "nt":
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            return
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    @staticmethod
    def _unlock(handle: IO[bytes]) -> None:
        if os.name == "nt":
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            return
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def running(path: Path) -> ServiceInfo | None:
    info = read(path)
    if info is None:
        return None
    if not is_alive(info.pid):
        return None
    return info


def lock_pid(path: Path) -> int | None:
    """Return the live pid holding the instance lock, or None."""
    try:
        text = path.read_text(encoding="ascii").strip()
    except OSError:
        return None
    if not text.isdigit():
        return None
    pid = int(text)
    return pid if is_alive(pid) else None
