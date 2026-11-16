"""Stateful/interactive nav widget (driven active/selected + actions)."""

from __future__ import annotations

from rich.console import Group
from textual import events
from textual.widget import Widget

from downcroc.cli.design.interaction.actions import Action, ActionKind
from downcroc.cli.design.interaction.focus import FocusState
from downcroc.cli.design.primitives.nav import NavItem
from downcroc.cli.design.primitives.text import label
from downcroc.cli.design.theme import DEFAULT, Theme
from downcroc.cli.design.widgets import PrimitiveAction


def _next_index(current: int, count: int) -> int:
    if count <= 0:
        return -1
    return min(current + 1, count - 1) if current >= 0 else 0


def _prev_index(current: int, count: int) -> int:
    if count <= 0:
        return -1
    return max(current - 1, 0) if current >= 0 else 0


class StatefulNavWidget(Widget):
    """Interactive/stateful nav list with callback-ready navigation hooks."""

    can_focus = True
    DEFAULT_CSS = "StatefulNavWidget { width: 40; height: auto; }"

    def __init__(
        self,
        items: list[tuple[str, dict]],
        theme: Theme = DEFAULT,
        *,
        active: int = 0,
        selected: int | None = None,
        on_navigate=None,
        id: str | None = None,
        classes: str | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes, name=name)
        self._items = items
        self._theme = theme
        self._active = max(0, min(active, len(items) - 1)) if items else -1
        self._selected = (
            self._active
            if selected is None
            else max(0, min(selected, len(items) - 1))
            if items
            else -1
        )
        self._hovered = -1
        self._focus = FocusState()
        self._on_navigate = on_navigate

    @property
    def active_index(self) -> int:
        return self._active

    @property
    def selected_index(self) -> int:
        return self._selected

    def set_active(self, index: int, *, emit: bool = False) -> None:
        if not self._items or not (0 <= index < len(self._items)):
            return
        self._active = index
        self._selected = index
        if emit:
            self._emit(ActionKind.ACTIVATED)
        self.refresh()

    def _emit(self, kind: ActionKind) -> None:
        if not (0 <= self._selected < len(self._items)):
            return
        text, opts = self._items[self._selected]
        target = str(opts.get("anchor") or opts.get("target") or text)
        payload = {"index": self._selected, "label": text, "anchor": opts.get("anchor")}
        self.post_message(PrimitiveAction(Action(kind, target=target, payload=payload)))
        if kind == ActionKind.ACTIVATED and self._on_navigate is not None:
            self._on_navigate(self._selected, target, payload)

    def on_focus(self, _: events.Focus) -> None:
        self._focus.focus(str(self._selected))
        self.refresh()

    def on_blur(self, _: events.Blur) -> None:
        self._focus.blur()
        self._hovered = -1
        self.refresh()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        idx = event.y if 0 <= event.y < len(self._items) else -1
        if idx != self._hovered:
            self._hovered = idx
            self.refresh()

    def on_leave(self, _: events.Leave) -> None:
        if self._hovered != -1:
            self._hovered = -1
            self.refresh()

    def on_click(self, event: events.Click) -> None:
        idx = event.y
        if 0 <= idx < len(self._items):
            self._selected = idx
            self._active = idx
            self.focus()
            self._emit(ActionKind.SELECTED)
            self._emit(ActionKind.ACTIVATED)
            self.refresh()

    def on_key(self, event: events.Key) -> None:
        if not self._items:
            return
        if event.key == "down":
            self._selected = _next_index(self._selected, len(self._items))
            self._emit(ActionKind.SELECTED)
            self.refresh()
            event.stop()
        elif event.key == "up":
            self._selected = _prev_index(self._selected, len(self._items))
            self._emit(ActionKind.SELECTED)
            self.refresh()
            event.stop()
        elif event.key in ("enter", "space"):
            self._active = self._selected
            self._emit(ActionKind.ACTIVATED)
            self.refresh()
            event.stop()

    def render(self) -> object:
        rows = []
        for i, (text, opts) in enumerate(self._items):
            state = "default"
            if self.has_focus and i == self._selected:
                state = "focus"
            elif i == self._hovered and i != self._selected:
                state = "hover"
            rows.append(
                NavItem(
                    text,
                    self._theme,
                    icon=str(opts.get("icon", "")),
                    active=(i == self._active),
                    indent=int(opts.get("indent", 0)),
                    badge_text=str(opts.get("badge", "")),
                    state=state,
                )
            )
        return Group(*rows) if rows else label("No navigation", self._theme)
