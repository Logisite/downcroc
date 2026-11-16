"""Stateful/interactive TOC widget with anchor-aware active tracking."""

from __future__ import annotations

from rich.console import Group
from textual import events
from textual.widget import Widget

from downcroc.cli.design.interaction.actions import Action, ActionKind
from downcroc.cli.design.primitives.nav import TocItem
from downcroc.cli.design.primitives.text import label
from downcroc.cli.design.theme import DEFAULT, Theme
from downcroc.cli.design.widgets import PrimitiveAction


class StatefulTocWidget(Widget):
    """Interactive/stateful TOC with active anchor and navigation hooks."""

    can_focus = True
    DEFAULT_CSS = "StatefulTocWidget { width: 32; height: auto; }"

    def __init__(
        self,
        items: list[tuple[str, dict]],
        theme: Theme = DEFAULT,
        *,
        active_anchor: str | None = None,
        on_navigate=None,
        id: str | None = None,
        classes: str | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes, name=name)
        self._items = items
        self._theme = theme
        self._active_anchor = active_anchor or (
            str(items[0][1].get("anchor", items[0][0])) if items else None
        )
        self._selected = 0
        self._hovered = -1
        self._on_navigate = on_navigate

    def set_items(
        self, items: list[tuple[str, dict]], *, active_anchor: str | None = None
    ) -> None:
        self._items = items
        if active_anchor is not None:
            self._active_anchor = active_anchor
        elif self._active_anchor is None and items:
            self._active_anchor = str(items[0][1].get("anchor", items[0][0]))
        self._selected = min(self._selected, max(len(items) - 1, 0))
        self.refresh()

    @property
    def active_anchor(self) -> str | None:
        return self._active_anchor

    def set_active_anchor(self, anchor: str | None, *, emit: bool = False) -> None:
        self._active_anchor = anchor
        for i, (text, opts) in enumerate(self._items):
            if str(opts.get("anchor", text)) == anchor:
                self._selected = i
                break
        if emit and anchor is not None:
            self._emit(ActionKind.SELECTED)
        self.refresh()

    def _emit(self, kind: ActionKind) -> None:
        if not (0 <= self._selected < len(self._items)):
            return
        text, opts = self._items[self._selected]
        anchor = str(opts.get("anchor", text))
        payload = {"index": self._selected, "label": text, "anchor": anchor}
        self.post_message(PrimitiveAction(Action(kind, target=anchor, payload=payload)))
        if kind == ActionKind.ACTIVATED and self._on_navigate is not None:
            self._on_navigate(self._selected, anchor, payload)

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
            text, opts = self._items[idx]
            self._active_anchor = str(opts.get("anchor", text))
            self.focus()
            self._emit(ActionKind.SELECTED)
            self._emit(ActionKind.ACTIVATED)
            self.refresh()

    def on_key(self, event: events.Key) -> None:
        if not self._items:
            return
        if event.key == "down":
            self._selected = min(self._selected + 1, len(self._items) - 1)
            self._emit(ActionKind.SELECTED)
            self.refresh()
            event.stop()
        elif event.key == "up":
            self._selected = max(self._selected - 1, 0)
            self._emit(ActionKind.SELECTED)
            self.refresh()
            event.stop()
        elif event.key in ("enter", "space"):
            text, opts = self._items[self._selected]
            self._active_anchor = str(opts.get("anchor", text))
            self._emit(ActionKind.ACTIVATED)
            self.refresh()
            event.stop()

    def render(self) -> object:
        rows = []
        for i, (text, opts) in enumerate(self._items):
            anchor = str(opts.get("anchor", text))
            state = "default"
            if self.has_focus and i == self._selected:
                state = "focus"
            elif i == self._hovered and i != self._selected:
                state = "hover"
            rows.append(
                TocItem(
                    text,
                    self._theme,
                    level=int(opts.get("level", 1)),
                    active=(anchor == self._active_anchor),
                    state=state,
                )
            )
        return Group(*rows) if rows else label("No headings", self._theme)
