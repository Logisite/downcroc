"""Normalized pointer event contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PointerKind(str, Enum):
    MOVE = "move"
    DOWN = "down"
    UP = "up"
    SCROLL = "scroll"


class PointerButton(str, Enum):
    NONE = "none"
    LEFT = "left"
    MIDDLE = "middle"
    RIGHT = "right"


@dataclass(frozen=True)
class PointerEvent:
    """Normalized pointer event in cell coordinates."""

    kind: PointerKind
    x: int
    y: int
    button: PointerButton = PointerButton.NONE
    shift: bool = False
    ctrl: bool = False
    meta: bool = False
    delta_x: int = 0
    delta_y: int = 0
