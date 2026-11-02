from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeState:
    sending_paused_at: str | None
    sending_paused_until: str | None
    sending_paused_reason: str | None
    updated_at: str

    @property
    def paused(self) -> bool:
        return self.sending_paused_at is not None
