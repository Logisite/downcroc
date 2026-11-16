"""Hit regions for painted/custom-rendered areas."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HitRegion:
    """Axis-aligned hit region in terminal cell coordinates."""

    id: str
    x: int
    y: int
    width: int
    height: int
    data: dict[str, str] | None = None

    def contains(self, x: int, y: int) -> bool:
        return self.x <= x < self.x + self.width and self.y <= y < self.y + self.height
