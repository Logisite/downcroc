"""Focus state contracts (separate from hover)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FocusState:
    """Tracks keyboard/pointer focus target."""

    target: str | None = None

    @property
    def is_focused(self) -> bool:
        return self.target is not None

    def focus(self, target: str) -> bool:
        changed = target != self.target
        self.target = target
        return changed

    def blur(self) -> bool:
        changed = self.target is not None
        self.target = None
        return changed
