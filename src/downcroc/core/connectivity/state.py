from __future__ import annotations

import threading


class ConnectivityState:
    """The one shared primitive every slice reads: is the internet up?

    A plain thread-safe flag with no I/O. The monitor owns flipping it;
    everyone else only reads ``online``.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._online = True
        self._since: str | None = None

    @property
    def online(self) -> bool:
        with self._lock:
            return self._online

    @property
    def since(self) -> str | None:
        with self._lock:
            return self._since

    def set(self, online: bool, since: str) -> None:
        with self._lock:
            self._online = online
            self._since = since
