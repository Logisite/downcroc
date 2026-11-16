"""Reusable Textual-aligned interactive wrappers for design primitives.

Phase 2: integrates Textual events/focus with interaction adapters
(state/hover/focus/actions/hit/pointer). No custom gesture/physics loops.
"""

from __future__ import annotations

from rich.text import Text
from textual import events
from textual.message import Message
from textual.widget import Widget

from downcroc.cli.design.interaction.actions import Action, ActionKind
from downcroc.cli.design.interaction.focus import FocusState
from downcroc.cli.design.interaction.hit import HitRegion
from downcroc.cli.design.interaction.hover import HoverState
from downcroc.cli.design.interaction.pointer import (
    PointerButton,
    PointerEvent,
    PointerKind,
)
from downcroc.cli.design.interaction.state import InteractionState, resolve_state
from downcroc.cli.design.primitives.button import Button
from downcroc.cli.design.primitives.card import Card
from downcroc.cli.design.primitives.code_panel import CodePanel, sample_panel
from downcroc.cli.design.primitives.nav import NavItem, TocItem
from downcroc.cli.design.primitives.text import breadcrumb, label
from downcroc.cli.design.theme import DEFAULT, Theme


def pointer_from_mouse(event: events.MouseEvent, kind: PointerKind) -> PointerEvent:
    """Normalize a Textual mouse event into a pointer contract (adapter)."""
    button = PointerButton.NONE
    btn = getattr(event, "button", 0)
    if btn == 1:
        button = PointerButton.LEFT
    elif btn == 2:
        button = PointerButton.MIDDLE
    elif btn == 3:
        button = PointerButton.RIGHT
    return PointerEvent(
        kind=kind,
        x=getattr(event, "x", 0),
        y=getattr(event, "y", 0),
        button=button,
        shift=getattr(event, "shift", False),
        ctrl=getattr(event, "ctrl", False),
        meta=getattr(event, "meta", False),
    )


class PrimitiveAction(Message):
    """Bubbled interaction action from a design widget."""

    def __init__(self, action: Action) -> None:
        super().__init__()
        self.action = action


class InteractiveButtonWidget(Widget):
    """Reusable Textual button wrapper with interaction adapters and actions."""

    can_focus = True
    DEFAULT_CSS = """
    InteractiveButtonWidget { width: auto; height: 1; }
    InteractiveButtonWidget:focus { }
    InteractiveButtonWidget:hover { }
    """

    def __init__(
        self,
        text: str,
        theme: Theme = DEFAULT,
        *,
        variant: str = "secondary",
        icon: str = "",
        target: str | None = None,
        disabled: bool = False,
        id: str | None = None,
        classes: str | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes, name=name)
        self._text = text
        self._theme = theme
        self._variant = variant
        self._icon = icon
        self._target = target or text
        self._disabled = disabled
        self._hover = HoverState()
        self._focus = FocusState()
        self._state = (
            InteractionState.DISABLED if disabled else InteractionState.DEFAULT
        )

    def _emit(self, kind: ActionKind, payload: dict | None = None) -> None:
        self.post_message(
            PrimitiveAction(Action(kind, target=self._target, payload=payload or {}))
        )

    def _sync_state(self, state: InteractionState | str) -> None:
        if self._disabled:
            state = InteractionState.DISABLED
        resolved = resolve_state(state)
        if self._state != resolved:
            self._state = resolved
            self.refresh()

    def on_enter(self, _: events.Enter) -> None:
        self._hover.enter(self._target)
        if not self._disabled and not self.has_focus:
            self._sync_state(InteractionState.HOVER)
            self._emit(ActionKind.HOVERED)

    def on_leave(self, _: events.Leave) -> None:
        self._hover.leave()
        if not self._disabled and not self.has_focus:
            self._sync_state(InteractionState.DEFAULT)

    def on_focus(self, _: events.Focus) -> None:
        self._focus.focus(self._target)
        if not self._disabled:
            self._sync_state(InteractionState.FOCUS)
            self._emit(ActionKind.FOCUSED)

    def on_blur(self, _: events.Blur) -> None:
        self._focus.blur()
        self._emit(ActionKind.BLURRED)
        if self._disabled:
            self._sync_state(InteractionState.DISABLED)
        elif self._hover.is_hovering:
            self._sync_state(InteractionState.HOVER)
        else:
            self._sync_state(InteractionState.DEFAULT)

    def on_mouse_down(self, _: events.MouseDown) -> None:
        if self._disabled:
            return
        self._sync_state(InteractionState.PRESSED)
        self._emit(ActionKind.PRESSED)

    def on_mouse_up(self, _: events.MouseUp) -> None:
        if self._disabled:
            return
        self._emit(ActionKind.TAPPED)
        if self.has_focus:
            self._sync_state(InteractionState.FOCUS)
        elif self._hover.is_hovering:
            self._sync_state(InteractionState.HOVER)
        else:
            self._sync_state(InteractionState.DEFAULT)

    def on_key(self, event: events.Key) -> None:
        if self._disabled:
            return
        if event.key in {"enter", "space"}:
            self._emit(ActionKind.ACTIVATED)
            event.stop()

    def render(self) -> object:
        return Button(
            self._text,
            self._theme,
            variant=self._variant,
            state=self._state.value,
            icon=self._icon,
        )


class FocusableCardWidget(Widget):
    """Focusable/selectable card wrapper (basic collection/card interaction)."""

    can_focus = True
    DEFAULT_CSS = """
    FocusableCardWidget { width: auto; height: auto; }
    FocusableCardWidget:focus { }
    """

    def __init__(
        self,
        title: str,
        body: str,
        theme: Theme = DEFAULT,
        *,
        width: int = 40,
        border: str | None = None,
        selected: bool = False,
        id: str | None = None,
        classes: str | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes, name=name)
        self._title = title
        self._body = body
        self._theme = theme
        self._width = width
        self._border = border
        self._selected = selected
        self._hover = HoverState()
        self._focus = FocusState()

    def on_enter(self, _: events.Enter) -> None:
        self._hover.enter(self._title)
        self.refresh()

    def on_leave(self, _: events.Leave) -> None:
        self._hover.leave()
        self.refresh()

    def on_focus(self, _: events.Focus) -> None:
        self._focus.focus(self._title)
        self.refresh()

    def on_blur(self, _: events.Blur) -> None:
        self._focus.blur()
        self.refresh()

    def on_mouse_down(self, _: events.MouseDown) -> None:
        self._selected = not self._selected
        self.post_message(
            PrimitiveAction(
                Action(
                    ActionKind.SELECTED,
                    target=self._title,
                    payload={"selected": self._selected},
                )
            )
        )
        self.refresh()

    def render(self) -> object:
        theme = self._theme
        fill = "bg_panel"
        if self._selected or self.has_focus:
            fill = "bg_selected"
        elif self._hover.is_hovering:
            fill = "bg_hover"
        border = (
            "hairline"
            if (self._border == "hairline" or self.has_focus or self._selected)
            else self._border
        )
        return Card(
            self._title, self._body, theme, width=self._width, fill=fill, border=border
        )


class NavListWidget(Widget):
    """Basic collection interaction for nav items: hover/selected + keyboard."""

    can_focus = True
    DEFAULT_CSS = """
    NavListWidget { width: 42; height: auto; }
    """

    def __init__(
        self,
        items: list[tuple[str, dict]],
        theme: Theme = DEFAULT,
        *,
        selected: int = 0,
        id: str | None = None,
        classes: str | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes, name=name)
        self._items = items
        self._theme = theme
        self._selected = max(0, min(selected, len(items) - 1)) if items else -1
        self._hovered = -1

    def _emit(self, kind: ActionKind, index: int) -> None:
        if 0 <= index < len(self._items):
            self.post_message(
                PrimitiveAction(
                    Action(kind, target=self._items[index][0], payload={"index": index})
                )
            )

    def on_mouse_move(self, event: events.MouseMove) -> None:
        idx = (
            getattr(event, "offset", event).y
            if hasattr(getattr(event, "offset", None), "y")
            else event.y
        )
        if 0 <= idx < len(self._items) and idx != self._hovered:
            self._hovered = idx
            self._emit(ActionKind.HOVERED, idx)
            self.refresh()

    def on_leave(self, _: events.Leave) -> None:
        if self._hovered != -1:
            self._hovered = -1
            self.refresh()

    def on_click(self, event: events.Click) -> None:
        idx = event.y
        if 0 <= idx < len(self._items):
            self._selected = idx
            self._emit(ActionKind.SELECTED, idx)
            self.refresh()

    def on_key(self, event: events.Key) -> None:
        if not self._items:
            return
        if event.key == "down":
            self._selected = min(self._selected + 1, len(self._items) - 1)
            self._emit(ActionKind.SELECTED, self._selected)
            self.refresh()
            event.stop()
        elif event.key == "up":
            self._selected = max(self._selected - 1, 0)
            self._emit(ActionKind.SELECTED, self._selected)
            self.refresh()
            event.stop()
        elif event.key == "enter":
            self._emit(ActionKind.ACTIVATED, self._selected)
            event.stop()

    def render(self) -> object:
        from rich.console import Group

        rows = []
        for i, (text, opts) in enumerate(self._items):
            state = "default"
            active = i == self._selected
            if self.has_focus and active:
                state = "focus"
            elif active:
                state = "active"
            elif i == self._hovered:
                state = "hover"
            rows.append(
                NavItem(
                    text,
                    self._theme,
                    icon=str(opts.get("icon", "")),
                    active=active,
                    indent=int(opts.get("indent", 0)),
                    badge_text=str(opts.get("badge", "")),
                    width=42,
                    state=state,
                )
            )
        return Group(*rows) if rows else label("No items", self._theme)


class TocListWidget(Widget):
    """Basic collection interaction for TOC items: hover/selected + keyboard."""

    can_focus = True
    DEFAULT_CSS = """
    TocListWidget { width: 36; height: auto; }
    """

    def __init__(
        self, items: list[tuple[str, int]], theme: Theme = DEFAULT, *, selected: int = 0
    ) -> None:
        super().__init__()
        self._items = items
        self._theme = theme
        self._selected = max(0, min(selected, len(items) - 1)) if items else -1
        self._hovered = -1

    def on_mouse_move(self, event: events.MouseMove) -> None:
        idx = event.y
        if 0 <= idx < len(self._items) and idx != self._hovered:
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
            self.post_message(
                PrimitiveAction(
                    Action(
                        ActionKind.SELECTED,
                        target=self._items[idx][0],
                        payload={"index": idx},
                    )
                )
            )
            self.refresh()

    def on_key(self, event: events.Key) -> None:
        if not self._items:
            return
        if event.key == "down":
            self._selected = min(self._selected + 1, len(self._items) - 1)
            self.refresh()
            event.stop()
        elif event.key == "up":
            self._selected = max(self._selected - 1, 0)
            self.refresh()
            event.stop()

    def render(self) -> object:
        from rich.console import Group

        rows = []
        for i, (text, level) in enumerate(self._items):
            active = i == self._selected
            state = (
                "focus"
                if (self.has_focus and active)
                else (
                    "active"
                    if active
                    else ("hover" if i == self._hovered else "default")
                )
            )
            rows.append(
                TocItem(text, self._theme, level=level, active=active, state=state)
            )
        return Group(*rows) if rows else label("No headings", self._theme)


class CopyableCodePanelWidget(Widget):
    """Textual-integrated code panel with precise copy hit-target and actions."""

    can_focus = True
    DEFAULT_CSS = """
    CopyableCodePanelWidget { width: 72; height: auto; }
    """

    def __init__(
        self,
        panel: CodePanel | None = None,
        theme: Theme = DEFAULT,
        *,
        id: str | None = None,
        classes: str | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes, name=name)
        self._panel = panel or sample_panel(theme)
        self._hover = HoverState()
        self._focus = FocusState()
        self._copied = False
        self._copy_hover = False

    def _copy_region(self) -> HitRegion:
        """Compute copy-button hit region in widget-local cell coords (chrome row 0)."""
        # Mirror CodePanel chrome layout: left chrome + gap + button + pad
        width = self._panel.width or 72
        btn = self._panel._button()  # visual state text
        btn_len = len(btn.plain)
        x = max(width - btn_len, 0)
        return HitRegion(id="copy", x=x, y=0, width=btn_len, height=1)

    def _sync(self) -> None:
        if self._copied:
            self._panel.button_state = "copied"
            self._panel.copied = True
        elif self.has_focus:
            self._panel.button_state = "focus"
            self._panel.copied = False
        elif self._copy_hover or self._hover.is_hovering:
            self._panel.button_state = "hover"
            self._panel.copied = False
        else:
            self._panel.button_state = "default"
            self._panel.copied = False
        self.refresh()

    def _emit(self, kind: ActionKind, payload: dict | None = None) -> None:
        self.post_message(
            PrimitiveAction(
                Action(
                    kind, target=self._panel.filename or "code", payload=payload or {}
                )
            )
        )

    def _pointer_in_copy(self, event: events.MouseEvent) -> bool:
        # Use normalized pointer coords (widget-local) and hit region.
        pe = pointer_from_mouse(event, PointerKind.DOWN)
        return self._copy_region().contains(pe.x, pe.y)

    def on_enter(self, _: events.Enter) -> None:
        self._hover.enter("code")
        self._copied = False
        self._sync()

    def on_leave(self, _: events.Leave) -> None:
        self._hover.leave()
        self._copy_hover = False
        self._copied = False
        self._sync()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        in_copy = self._copy_region().contains(event.x, event.y)
        if in_copy != self._copy_hover:
            self._copy_hover = in_copy
            self._sync()

    def on_focus(self, _: events.Focus) -> None:
        self._focus.focus("code")
        self._emit(ActionKind.FOCUSED)
        self._sync()

    def on_blur(self, _: events.Blur) -> None:
        self._focus.blur()
        self._emit(ActionKind.BLURRED)
        self._sync()

    def on_click(self, event: events.Click) -> None:
        if self._pointer_in_copy(event) or event.y == 0:
            ok = self._panel.copy()
            self._copied = ok
            self._emit(ActionKind.COPIED, {"ok": ok})
            self._sync()

    def on_key(self, event: events.Key) -> None:
        if event.key in {"enter", "space"}:
            ok = self._panel.copy()
            self._copied = ok
            self._emit(ActionKind.COPIED, {"ok": ok})
            self._sync()
            event.stop()

    def render(self) -> object:
        return self._panel


class InteractiveNavItemWidget(Widget):
    """Standalone interactive nav item wrapper."""

    can_focus = True
    DEFAULT_CSS = """
    InteractiveNavItemWidget { width: 40; height: 1; }
    """

    def __init__(
        self,
        text: str,
        theme: Theme = DEFAULT,
        *,
        icon: str = "",
        active: bool = False,
        indent: int = 0,
        badge_text: str = "",
        id: str | None = None,
        classes: str | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes, name=name)
        self._text = text
        self._theme = theme
        self._icon = icon
        self._active = active
        self._indent = indent
        self._badge_text = badge_text
        self._hover = HoverState()
        self._focus = FocusState()

    def _emit(self, kind: ActionKind) -> None:
        self.post_message(PrimitiveAction(Action(kind, target=self._text)))

    def _state(self) -> str:
        if self._focus.is_focused and self.has_focus:
            return "focus"
        if self._active:
            return "active"
        if self._hover.is_hovering:
            return "hover"
        return "default"

    def on_enter(self, _: events.Enter) -> None:
        self._hover.enter(self._text)
        self._emit(ActionKind.HOVERED)
        self.refresh()

    def on_leave(self, _: events.Leave) -> None:
        self._hover.leave()
        self.refresh()

    def on_focus(self, _: events.Focus) -> None:
        self._focus.focus(self._text)
        self._emit(ActionKind.FOCUSED)
        self.refresh()

    def on_blur(self, _: events.Blur) -> None:
        self._focus.blur()
        self._emit(ActionKind.BLURRED)
        self.refresh()

    def on_mouse_down(self, _: events.MouseDown) -> None:
        self._active = not self._active
        self._emit(ActionKind.SELECTED)
        self.refresh()

    def on_key(self, event: events.Key) -> None:
        if event.key in {"enter", "space"}:
            self._active = not self._active
            self._emit(ActionKind.ACTIVATED)
            self.refresh()
            event.stop()

    def render(self) -> object:
        return NavItem(
            self._text,
            self._theme,
            icon=self._icon,
            active=self._active,
            indent=self._indent,
            badge_text=self._badge_text,
            width=40,
            state=self._state(),
        )


class InteractiveTocItemWidget(Widget):
    """Standalone interactive TOC item wrapper."""

    can_focus = True
    DEFAULT_CSS = """
    InteractiveTocItemWidget { width: 36; height: 1; }
    """

    def __init__(
        self,
        text: str,
        theme: Theme = DEFAULT,
        *,
        level: int = 1,
        active: bool = False,
        id: str | None = None,
        classes: str | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes, name=name)
        self._text = text
        self._theme = theme
        self._level = level
        self._active = active
        self._hover = HoverState()
        self._focus = FocusState()

    def _emit(self, kind: ActionKind) -> None:
        self.post_message(PrimitiveAction(Action(kind, target=self._text)))

    def _state(self) -> str:
        if self._focus.is_focused and self.has_focus:
            return "focus"
        if self._active:
            return "active"
        if self._hover.is_hovering:
            return "hover"
        return "default"

    def on_enter(self, _: events.Enter) -> None:
        self._hover.enter(self._text)
        self.refresh()

    def on_leave(self, _: events.Leave) -> None:
        self._hover.leave()
        self.refresh()

    def on_focus(self, _: events.Focus) -> None:
        self._focus.focus(self._text)
        self._emit(ActionKind.FOCUSED)
        self.refresh()

    def on_blur(self, _: events.Blur) -> None:
        self._focus.blur()
        self._emit(ActionKind.BLURRED)
        self.refresh()

    def on_mouse_down(self, _: events.MouseDown) -> None:
        self._active = not self._active
        self._emit(ActionKind.SELECTED)
        self.refresh()

    def render(self) -> object:
        return TocItem(
            self._text,
            self._theme,
            level=self._level,
            active=self._active,
            state=self._state(),
        )


class InteractiveLinkWidget(Widget):
    """Interactive link render helper (focus/hover/activate) with OSC 8 preserved."""

    can_focus = True
    DEFAULT_CSS = """
    InteractiveLinkWidget { width: auto; height: 1; }
    """

    def __init__(
        self,
        text: str,
        theme: Theme = DEFAULT,
        *,
        href: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes, name=name)
        self._text = text
        self._theme = theme
        self._href = href
        self._hover = HoverState()
        self._focus = FocusState()

    def _emit(self, kind: ActionKind) -> None:
        self.post_message(
            PrimitiveAction(
                Action(kind, target=self._text, payload={"href": self._href or ""})
            )
        )

    def _state(self) -> str:
        if self._focus.is_focused and self.has_focus:
            return "focus"
        if self._hover.is_hovering:
            return "hover"
        return "default"

    def on_enter(self, _: events.Enter) -> None:
        self._hover.enter(self._text)
        self.refresh()

    def on_leave(self, _: events.Leave) -> None:
        self._hover.leave()
        self.refresh()

    def on_focus(self, _: events.Focus) -> None:
        self._focus.focus(self._text)
        self.refresh()

    def on_blur(self, _: events.Blur) -> None:
        self._focus.blur()
        self.refresh()

    def on_click(self, _: events.Click) -> None:
        self._emit(ActionKind.ACTIVATED)

    def on_key(self, event: events.Key) -> None:
        if event.key in {"enter", "space"}:
            self._emit(ActionKind.ACTIVATED)
            event.stop()

    def render(self) -> object:
        from downcroc.cli.design.primitives.text import link_text

        return link_text(self._text, self._theme, href=self._href, state=self._state())


class InteractiveKeycapWidget(Widget):
    """Interactive keycap chip (hover/focus/pressed visual states)."""

    can_focus = True
    DEFAULT_CSS = """
    InteractiveKeycapWidget { width: auto; height: 1; }
    """

    def __init__(
        self,
        key: str,
        theme: Theme = DEFAULT,
        *,
        id: str | None = None,
        classes: str | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes, name=name)
        self._key = key
        self._theme = theme
        self._hover = HoverState()
        self._focus = FocusState()
        self._pressed = False

    def _emit(self, kind: ActionKind) -> None:
        self.post_message(PrimitiveAction(Action(kind, target=self._key)))

    def on_enter(self, _: events.Enter) -> None:
        self._hover.enter(self._key)
        self.refresh()

    def on_leave(self, _: events.Leave) -> None:
        self._hover.leave()
        self._pressed = False
        self.refresh()

    def on_focus(self, _: events.Focus) -> None:
        self._focus.focus(self._key)
        self.refresh()

    def on_blur(self, _: events.Blur) -> None:
        self._focus.blur()
        self.refresh()

    def on_mouse_down(self, _: events.MouseDown) -> None:
        self._pressed = True
        self._emit(ActionKind.PRESSED)
        self.refresh()

    def on_mouse_up(self, _: events.MouseUp) -> None:
        self._pressed = False
        self._emit(ActionKind.TAPPED)
        self.refresh()

    def render(self) -> object:
        from rich.text import Text

        theme = self._theme
        pad = " " * theme.space_1
        bg = "bg_raised"
        fg = "fg_primary"
        if self._pressed:
            bg = "bg_active"
        elif self.has_focus and self._focus.is_focused:
            bg = "bg_hover"
            fg = "accent_strong"
        elif self._hover.is_hovering:
            bg = "bg_hover"
        return Text(f"{pad}{self._key}{pad}", style=theme.style(fg, on=bg, bold=True))


class SelectableListWidget(Widget):
    """Basic list collection interaction: hover/selected rows via Textual events."""

    can_focus = True
    DEFAULT_CSS = """
    SelectableListWidget { width: 44; height: auto; }
    """

    def __init__(
        self,
        items: list[str],
        theme: Theme = DEFAULT,
        *,
        selected: int = 0,
        id: str | None = None,
        classes: str | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes, name=name)
        self._items = items
        self._theme = theme
        self._selected = max(0, min(selected, len(items) - 1)) if items else -1
        self._hovered = -1

    def _emit(self, kind: ActionKind) -> None:
        target = (
            self._items[self._selected]
            if 0 <= self._selected < len(self._items)
            else None
        )
        self.post_message(
            PrimitiveAction(
                Action(kind, target=target, payload={"index": self._selected})
            )
        )

    def on_mouse_move(self, event: events.MouseMove) -> None:
        idx = event.y
        if 0 <= idx < len(self._items) and idx != self._hovered:
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
            self._emit(ActionKind.SELECTED)
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

    def render(self) -> object:
        from rich.console import Group
        from rich.text import Text

        theme = self._theme
        rows = []
        for i, item in enumerate(self._items):
            prefix = "▌ " if i == self._selected else "  "
            marker = "•"
            style = theme.style("fg_secondary")
            bg = "bg_page"
            if self.has_focus and i == self._selected or i == self._selected:
                style = theme.style("accent_strong", bold=True)
                bg = "bg_selected"
            elif i == self._hovered:
                style = theme.style("fg_primary")
                bg = "bg_hover"
            row = Text()
            row.append(
                prefix,
                style=theme.style(
                    "accent" if i == self._selected else "fg_faint", on=bg
                ),
            )
            row.append(f"{marker} ", style=theme.style("accent", on=bg))
            row.append(item, style=f"{style} on {getattr(theme, bg, theme.bg_page)}")
            rows.append(row)
        return Group(*rows) if rows else label("No items", theme)


class SelectableTableWidget(Widget):
    """Basic table collection interaction: selected/hovered row styling."""

    can_focus = True
    DEFAULT_CSS = """
    SelectableTableWidget { width: auto; height: auto; }
    """

    def __init__(
        self,
        headers: list[str],
        rows: list[list[str]],
        theme: Theme = DEFAULT,
        *,
        selected: int = 0,
        width: int | None = None,
        data_offset: int = 3,
        id: str | None = None,
        classes: str | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes, name=name)
        self._headers = headers
        self._rows = rows
        self._theme = theme
        self._selected = max(0, min(selected, len(rows) - 1)) if rows else -1
        self._hovered = -1
        self._width = width
        # Approximate first data row y in rendered SQUARE table
        # (top border + header + separator = 3 for default settings).
        self._data_offset = max(0, int(data_offset))

    def _emit(self, kind: ActionKind) -> None:
        target = (
            ",".join(self._rows[self._selected])
            if 0 <= self._selected < len(self._rows)
            else None
        )
        self.post_message(
            PrimitiveAction(
                Action(kind, target=target, payload={"index": self._selected})
            )
        )

    def _row_from_y(self, y: int) -> int | None:
        idx = y - self._data_offset
        if 0 <= idx < len(self._rows):
            return idx
        return None

    def on_mouse_move(self, event: events.MouseMove) -> None:
        idx = self._row_from_y(event.y)
        if idx is not None and idx != self._hovered:
            self._hovered = idx
            self.refresh()

    def on_leave(self, _: events.Leave) -> None:
        if self._hovered != -1:
            self._hovered = -1
            self.refresh()

    def on_click(self, event: events.Click) -> None:
        idx = self._row_from_y(event.y)
        if idx is not None:
            self._selected = idx
            self._emit(ActionKind.SELECTED)
            self.refresh()

    def on_key(self, event: events.Key) -> None:
        if not self._rows:
            return
        if event.key == "down":
            self._selected = min(self._selected + 1, len(self._rows) - 1)
            self._emit(ActionKind.SELECTED)
            self.refresh()
            event.stop()
        elif event.key == "up":
            self._selected = max(self._selected - 1, 0)
            self._emit(ActionKind.SELECTED)
            self.refresh()
            event.stop()
        elif event.key == "enter":
            self._emit(ActionKind.ACTIVATED)
            event.stop()

    def render(self) -> object:
        from downcroc.cli.design.primitives.table_view import TableView

        rows = []
        for i, row in enumerate(self._rows):
            style = None
            if self.has_focus and i == self._selected:
                style = "focus"
            elif i == self._selected:
                style = "selected"
            elif i == self._hovered:
                style = "hover"
            if style:
                rows.append({"cells": row, "style": style})
            else:
                rows.append(row)
        return TableView(
            self._headers,
            rows,
            self._theme,
            width=self._width,
            zebra=False,
            compact=True,
        )


class InteractiveBreadcrumbWidget(Widget):
    """Focusable breadcrumb with per-item hit targets, actions, and history hooks."""

    can_focus = True
    DEFAULT_CSS = """
    InteractiveBreadcrumbWidget { width: auto; height: 1; }
    """

    def __init__(
        self,
        items: list[str] | list[tuple[str, str]],
        theme: Theme = DEFAULT,
        *,
        selected: int | None = None,
        separator: str = " › ",
        track_history: bool = True,
        on_navigate=None,
        id: str | None = None,
        classes: str | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes, name=name)
        norm: list[tuple[str, str]] = []
        for item in items:
            if isinstance(item, tuple):
                norm.append((str(item[0]), str(item[1])))
            else:
                norm.append((str(item), str(item)))
        self._items = norm
        self._theme = theme
        self._selected = (
            len(norm) - 1
            if selected is None and norm
            else max(0, min(selected, len(norm) - 1))
            if norm and selected is not None
            else -1
        )
        self._hovered = -1
        self._separator = separator
        self._focus = FocusState()
        self._history: list[int] = []
        self._track_history = track_history
        self._on_navigate = on_navigate

    @property
    def history(self) -> list[int]:
        return list(self._history)

    @property
    def selected_index(self) -> int:
        return self._selected

    @property
    def items(self) -> list[tuple[str, str]]:
        return list(self._items)

    def set_items(
        self, items: list[str] | list[tuple[str, str]], *, selected: int | None = None
    ) -> None:
        norm: list[tuple[str, str]] = []
        for item in items:
            if isinstance(item, tuple):
                norm.append((str(item[0]), str(item[1])))
            else:
                norm.append((str(item), str(item)))
        self._items = norm
        self._history.clear()
        self._selected = (
            len(norm) - 1
            if selected is None and norm
            else max(0, min(selected, len(norm) - 1))
            if norm and selected is not None
            else -1
        )
        self.refresh()

    def _emit(self, kind: ActionKind, *, extra: dict | None = None) -> None:
        target = (
            self._items[self._selected][1]
            if 0 <= self._selected < len(self._items)
            else None
        )
        label = (
            self._items[self._selected][0]
            if 0 <= self._selected < len(self._items)
            else None
        )
        payload = {"index": self._selected, "label": label}
        if extra:
            payload.update(extra)
        action = Action(kind, target=target, payload=payload)
        self.post_message(PrimitiveAction(action))
        if kind == ActionKind.ACTIVATED and self._on_navigate is not None:
            self._on_navigate(self._selected, target, label)

    def select_index(
        self, idx: int, *, record_history: bool = True, emit: bool = True
    ) -> None:
        if not self._items or not (0 <= idx < len(self._items)):
            return
        prev = self._selected
        if record_history and self._track_history and prev != idx and prev >= 0:
            self._history.append(prev)
        self._selected = idx
        if emit:
            self._emit(ActionKind.SELECTED, extra={"previous": prev})
            self._emit(ActionKind.ACTIVATED, extra={"previous": prev})
        self.refresh()

    def go_back(self) -> bool:
        if not self._history:
            return False
        idx = self._history.pop()
        prev = self._selected
        self._selected = idx
        self._emit(ActionKind.SELECTED, extra={"from_history": True, "previous": prev})
        self._emit(ActionKind.ACTIVATED, extra={"from_history": True, "previous": prev})
        self.refresh()
        return True

    def _item_segments(self) -> list[tuple[int, int, int]]:
        segs: list[tuple[int, int, int]] = []
        x = 0
        sep_len = len(self._separator)
        for i, (text, _) in enumerate(self._items):
            start = x
            x += len(text)
            segs.append((i, start, x))
            if i < len(self._items) - 1:
                x += sep_len
        return segs

    def _index_at_x(self, x: int) -> int | None:
        for i, start, end in self._item_segments():
            if start <= x < end:
                return i
        return None

    def on_focus(self, _: events.Focus) -> None:
        target = (
            self._items[self._selected][1]
            if 0 <= self._selected < len(self._items)
            else "breadcrumb"
        )
        self._focus.focus(target)
        self._emit(ActionKind.FOCUSED)
        self.refresh()

    def on_blur(self, _: events.Blur) -> None:
        self._focus.blur()
        self._hovered = -1
        self._emit(ActionKind.BLURRED)
        self.refresh()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        idx = self._index_at_x(event.x)
        if idx is None:
            if self._hovered != -1:
                self._hovered = -1
                self.refresh()
            return
        if idx != self._hovered:
            self._hovered = idx
            self.refresh()

    def on_leave(self, _: events.Leave) -> None:
        if self._hovered != -1:
            self._hovered = -1
            self.refresh()

    def on_click(self, event: events.Click) -> None:
        idx = self._index_at_x(event.x)
        if idx is None:
            return
        self.focus()
        self.select_index(idx, record_history=True, emit=True)

    def on_key(self, event: events.Key) -> None:
        if not self._items:
            return
        if event.key in ("right", "down"):
            self.select_index(
                min(self._selected + 1, len(self._items) - 1),
                record_history=False,
                emit=True,
            )
            event.stop()
        elif event.key in ("left", "up"):
            self.select_index(
                max(self._selected - 1, 0), record_history=False, emit=True
            )
            event.stop()
        elif event.key in ("enter", "space"):
            self._emit(ActionKind.ACTIVATED)
            event.stop()
        elif event.key == "backspace":
            self.go_back()
            event.stop()

    def render(self) -> object:
        if not self._items:
            return Text("")
        items: list[tuple[str, str]] = []
        for i, (text, _) in enumerate(self._items):
            if self.has_focus and i == self._selected:
                state = "focus"
            elif i == self._hovered and i != self._selected:
                state = "hover"
            elif i == self._selected:
                state = "active"
            else:
                state = "default"
            items.append((text, state))
        return breadcrumb(items, self._theme, separator=self._separator)


class InteractivePagerWidget(Widget):
    """Interactive previous/next pager with actions and callback-ready targets."""

    can_focus = True
    DEFAULT_CSS = """
    InteractivePagerWidget { width: auto; height: auto; }
    """

    def __init__(
        self,
        theme: Theme = DEFAULT,
        *,
        prev_label: str = "",
        prev_target: str = "",
        next_label: str = "",
        next_target: str = "",
        width: int = 72,
        on_navigate=None,
        id: str | None = None,
        classes: str | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes, name=name)
        self._theme = theme
        self._prev_label = prev_label
        self._prev_target = prev_target
        self._next_label = next_label
        self._next_target = next_target
        self._width = width
        self._on_navigate = on_navigate
        self._focus_side: str | None = (
            "next" if next_label else "prev" if prev_label else None
        )
        self._hover_side: str | None = None
        self._focus = FocusState()

    def _sides(self) -> list[str]:
        sides = []
        if self._prev_label:
            sides.append("prev")
        if self._next_label:
            sides.append("next")
        return sides

    def _emit(self, kind: ActionKind, side: str) -> None:
        if side == "prev":
            label, target = self._prev_label, self._prev_target
        else:
            label, target = self._next_label, self._next_target
        payload = {"side": side, "label": label, "target": target}
        self.post_message(
            PrimitiveAction(Action(kind, target=target or side, payload=payload))
        )
        if kind == ActionKind.ACTIVATED and self._on_navigate is not None:
            self._on_navigate(side, target, label)

    def on_focus(self, _: events.Focus) -> None:
        if self._focus_side is None:
            sides = self._sides()
            self._focus_side = sides[0] if sides else None
        self._focus.focus(self._focus_side or "pager")
        self.refresh()

    def on_blur(self, _: events.Blur) -> None:
        self._focus.blur()
        self._hover_side = None
        self.refresh()

    def _side_from_x(self, x: int) -> str | None:
        # approximate split: left half prev, right half next
        mid = max(self._width // 2, 1)
        if x < mid and self._prev_label:
            return "prev"
        if x >= mid and self._next_label:
            return "next"
        if self._prev_label and not self._next_label:
            return "prev"
        if self._next_label and not self._prev_label:
            return "next"
        return None

    def on_mouse_move(self, event: events.MouseMove) -> None:
        side = self._side_from_x(event.x)
        if side != self._hover_side:
            self._hover_side = side
            self.refresh()

    def on_leave(self, _: events.Leave) -> None:
        if self._hover_side is not None:
            self._hover_side = None
            self.refresh()

    def on_click(self, event: events.Click) -> None:
        side = self._side_from_x(event.x)
        if side is None:
            return
        self._focus_side = side
        self.focus()
        self._emit(ActionKind.SELECTED, side)
        self._emit(ActionKind.ACTIVATED, side)
        self.refresh()

    def on_key(self, event: events.Key) -> None:
        sides = self._sides()
        if not sides:
            return
        if event.key in ("left", "shift+tab"):
            if "prev" in sides:
                self._focus_side = "prev"
                self._emit(ActionKind.SELECTED, "prev")
                self.refresh()
            event.stop()
        elif event.key in ("right", "tab"):
            if "next" in sides:
                self._focus_side = "next"
                self._emit(ActionKind.SELECTED, "next")
                self.refresh()
            event.stop()
        elif event.key in ("enter", "space"):
            if self._focus_side in sides:
                self._emit(ActionKind.ACTIVATED, self._focus_side)
            event.stop()

    def render(self) -> object:
        from downcroc.cli.design.components.pager import Pager

        prev_state = "default"
        next_state = "default"
        if self.has_focus and self._focus_side == "prev":
            prev_state = "focus"
        elif self._hover_side == "prev":
            prev_state = "hover"
        if self.has_focus and self._focus_side == "next":
            next_state = "focus"
        elif self._hover_side == "next":
            next_state = "hover"
        return Pager(
            self._theme,
            prev_label=self._prev_label,
            prev_target=self._prev_target,
            next_label=self._next_label,
            next_target=self._next_target,
            width=self._width,
            prev_state=prev_state,
            next_state=next_state,
        )
