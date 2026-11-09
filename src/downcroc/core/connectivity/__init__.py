from __future__ import annotations

from typing import Any

__all__ = ["ConnectivityMonitor", "ConnectivityState"]


def __getattr__(name: str) -> Any:
    if name == "ConnectivityMonitor":
        from downcroc.core.connectivity.monitor import ConnectivityMonitor

        return ConnectivityMonitor
    if name == "ConnectivityState":
        from downcroc.core.connectivity.state import ConnectivityState

        return ConnectivityState
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
