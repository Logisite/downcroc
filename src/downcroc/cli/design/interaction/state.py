"""Interaction state enums and simple style mapping hooks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class InteractionState(str, Enum):
    """Visual/interaction states shared by actionable primitives."""

    DEFAULT = "default"
    HOVER = "hover"
    FOCUS = "focus"
    PRESSED = "pressed"
    ACTIVE = "active"
    SELECTED = "selected"
    DISABLED = "disabled"


@dataclass(frozen=True)
class StateStyles:
    """Optional resolved style tokens for a given interaction state."""

    fg: str | None = None
    bg: str | None = None
    border: str | None = None
    bold: bool = False


def resolve_state(state: InteractionState | str) -> InteractionState:
    """Normalize string/enum state values."""
    if isinstance(state, InteractionState):
        return state
    try:
        return InteractionState(state)
    except ValueError:
        return InteractionState.DEFAULT
