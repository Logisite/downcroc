"""Gesture detection contracts (tap/press/drag/swipe)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GestureKind(str, Enum):
    TAP = "tap"
    DOUBLE_TAP = "double_tap"
    LONG_PRESS = "long_press"
    DRAG = "drag"
    SWIPE = "swipe"


@dataclass(frozen=True)
class Gesture:
    """Recognized gesture event."""

    kind: GestureKind
    x: int
    y: int
    dx: int = 0
    dy: int = 0
    duration_ms: int = 0
