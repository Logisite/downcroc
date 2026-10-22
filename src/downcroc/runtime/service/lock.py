from __future__ import annotations

import fcntl
import os
from pathlib import Path
from typing import IO

from downcroc.runtime.service.registry import ServiceInfo, read


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
        self._handle: IO[str] | None = None

    def acquire(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        handle = self._path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            raise AlreadyRunning(None) from None
        handle.seek(0)
        handle.truncate()
        handle.write(str(os.getpid()))
        handle.flush()
        self._handle = handle

    def release(self) -> None:
        if self._handle is None:
            return
        try:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        finally:
            self._handle.close()
            self._handle = None


def running(path: Path) -> ServiceInfo | None:
    info = read(path)
    if info is None:
        return None
    try:
        os.kill(info.pid, 0)
    except ProcessLookupError:
        return None
    except PermissionError:
        return info
    return info
