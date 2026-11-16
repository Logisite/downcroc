"""Event-based gesture recognition helpers (no timers/physics loops).

Derives tap/drag/swipe/long-press-like semantics from Textual mouse events
using position deltas and optional timestamps provided by callers.
"""

from __future__ import annotations

from dataclasses import dataclass

from downcroc.cli.design.interaction.gestures import Gesture, GestureKind


@dataclass
class GestureTracker:
    """Track a pointer press/release sequence and classify on release."""

    drag_threshold: int = 2
    swipe_threshold: int = 8
    long_press_ms: int = 500

    _x: int = 0
    _y: int = 0
    _t_ms: int = 0
    _pressed: bool = False

    def press(self, x: int, y: int, t_ms: int = 0) -> None:
        self._x = x
        self._y = y
        self._t_ms = t_ms
        self._pressed = True

    def release(self, x: int, y: int, t_ms: int = 0) -> Gesture | None:
        if not self._pressed:
            return None
        self._pressed = False
        dx = x - self._x
        dy = y - self._y
        adx, ady = abs(dx), abs(dy)
        duration = max(0, t_ms - self._t_ms) if t_ms and self._t_ms else 0
        if adx >= self.swipe_threshold or ady >= self.swipe_threshold:
            return Gesture(GestureKind.SWIPE, x, y, dx, dy, duration)
        if adx > self.drag_threshold or ady > self.drag_threshold:
            return Gesture(GestureKind.DRAG, x, y, dx, dy, duration)
        if duration >= self.long_press_ms:
            return Gesture(GestureKind.LONG_PRESS, x, y, dx, dy, duration)
        return Gesture(GestureKind.TAP, x, y, dx, dy, duration)

    def cancel(self) -> None:
        self._pressed = False
