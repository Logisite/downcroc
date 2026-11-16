"""Interaction and state contracts for design primitives (Phase 2 base).

These types are intended as thin contracts/adapters to integrate with Textual's
events, focus, and hit-testing rather than a hand-rolled terminal input engine.
"""

from downcroc.cli.design.interaction.actions import Action, ActionKind
from downcroc.cli.design.interaction.focus import FocusState
from downcroc.cli.design.interaction.gestures import Gesture, GestureKind
from downcroc.cli.design.interaction.hit import HitRegion
from downcroc.cli.design.interaction.hover import HoverState
from downcroc.cli.design.interaction.pointer import (
    PointerButton,
    PointerEvent,
    PointerKind,
)
from downcroc.cli.design.interaction.scroll_physics import ScrollState
from downcroc.cli.design.interaction.state import InteractionState

__all__ = [
    "Action",
    "ActionKind",
    "FocusState",
    "Gesture",
    "GestureKind",
    "HitRegion",
    "HoverState",
    "InteractionState",
    "PointerButton",
    "PointerEvent",
    "PointerKind",
    "ScrollState",
]
