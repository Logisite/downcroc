"""Stateful nav/toc container composites (foundation, driven state)."""

from __future__ import annotations

from rich.console import Console, ConsoleOptions, Group, RenderResult

from downcroc.cli.design.primitives.nav import NavItem, TocItem
from downcroc.cli.design.primitives.section_header import SectionHeader
from downcroc.cli.design.primitives.spacer import spacer
from downcroc.cli.design.theme import Theme


class StatefulNav:
    """Nav container rendering active/selected/focused item from driven state."""

    def __init__(
        self,
        items: list[tuple[str, dict]],
        theme: Theme,
        *,
        title: str = "",
        active_index: int = 0,
        selected_index: int | None = None,
        focused: bool = False,
        width: int = 40,
    ) -> None:
        self.items = items
        self.theme = theme
        self.title = title
        self.active_index = active_index
        self.selected_index = (
            selected_index if selected_index is not None else active_index
        )
        self.focused = focused
        self.width = width

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        parts: list[object] = []
        if self.title:
            parts.append(SectionHeader(self.title, self.theme))
        for i, (text, opts) in enumerate(self.items):
            state = "default"
            if self.focused and i == self.selected_index:
                state = "focus"
            elif i == self.active_index or i == self.selected_index:
                state = "active"
            parts.append(
                NavItem(
                    text,
                    self.theme,
                    icon=str(opts.get("icon", "")),
                    active=(i == self.active_index),
                    indent=int(opts.get("indent", 0)),
                    badge_text=str(opts.get("badge", "")),
                    width=self.width,
                    state=state if state != "active" else "default",
                )
            )
        parts.append(spacer(1, theme=self.theme))
        yield Group(*parts)


class StatefulToc:
    """TOC container rendering active anchor/selection from driven state."""

    def __init__(
        self,
        items: list[tuple[str, dict]],
        theme: Theme,
        *,
        title: str = "On this page",
        active_anchor: str | None = None,
        selected_anchor: str | None = None,
        focused: bool = False,
    ) -> None:
        self.items = items
        self.theme = theme
        self.title = title
        self.active_anchor = active_anchor
        self.selected_anchor = selected_anchor or active_anchor
        self.focused = focused

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        parts: list[object] = [SectionHeader(self.title, self.theme)]
        for text, opts in self.items:
            anchor = str(opts.get("anchor", text))
            state = "default"
            if self.focused and anchor == self.selected_anchor:
                state = "focus"
            elif anchor == self.active_anchor:
                state = "active"
            parts.append(
                TocItem(
                    text,
                    self.theme,
                    level=int(opts.get("level", 1)),
                    active=(anchor == self.active_anchor),
                    state=state if state != "active" else "default",
                )
            )
        parts.append(spacer(1, theme=self.theme))
        yield Group(*parts)
