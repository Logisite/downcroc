"""Scroll and anchor motion state helpers (minimal base)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ScrollState:
    """Minimal scroll state for containers/anchors."""

    offset: float = 0.0
    velocity: float = 0.0
    min_offset: float = 0.0
    max_offset: float = 0.0

    def clamp(self) -> None:
        if self.offset < self.min_offset:
            self.offset = self.min_offset
            self.velocity = 0.0
        elif self.offset > self.max_offset:
            self.offset = self.max_offset
            self.velocity = 0.0

    def apply_delta(self, delta: float) -> None:
        self.offset += delta
        self.clamp()
