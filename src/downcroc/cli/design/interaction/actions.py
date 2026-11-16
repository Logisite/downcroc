"""Standard bubbled actions/messages for interactive primitives."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ActionKind(str, Enum):
    HOVERED = "hovered"
    PRESSED = "pressed"
    TAPPED = "tapped"
    LONG_PRESSED = "long_pressed"
    FOCUSED = "focused"
    BLURRED = "blurred"
    SELECTED = "selected"
    COPIED = "copied"
    DISMISSED = "dismissed"
    ACTIVATED = "activated"


@dataclass(frozen=True)
class Action:
    """A UI action emitted by a primitive or interaction controller."""

    kind: ActionKind
    target: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
