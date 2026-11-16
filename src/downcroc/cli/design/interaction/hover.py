"""Hover state tracking contracts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class HoverState:
    """Tracks current hover target and transition intent."""

    target: str | None = None
    entered_at: float | None = None

    @property
    def is_hovering(self) -> bool:
        return self.target is not None

    def enter(self, target: str, at: float | None = None) -> bool:
        changed = target != self.target
        self.target = target
        self.entered_at = at
        return changed

    def leave(self) -> bool:
        changed = self.target is not None
        self.target = None
        self.entered_at = None
        return changed
