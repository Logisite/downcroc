from __future__ import annotations

from typing import Protocol


class WatcherControl(Protocol):
    def account_changed(self, account_id: str, enabled: bool) -> None: ...
