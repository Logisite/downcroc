"""Collapsible primitive/composition (shadcn Collapsible mapping, static/render-state)."""

from __future__ import annotations

from rich.console import Console, ConsoleOptions, Group, RenderResult
from rich.text import Text

from downcroc.cli.design.theme import DEFAULT, Theme


class Collapsible:
    """A collapsible section: trigger label + optional content when open."""

    def __init__(
        self,
        title: str,
        content: object | None = None,
        *,
        open: bool = False,
        theme: Theme = DEFAULT,
        level: int = 0,
    ) -> None:
        self.title = title
        self.content = content
        self.open = open
        self.theme = theme
        self.level = level

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        indent = "  " * max(self.level, 0)
        marker = "▾" if self.open else "▸"
        line = Text(indent)
        line.append(f"{marker} ", style=self.theme.style("fg_muted"))
        line.append(self.title, style=self.theme.style("fg_secondary", bold=self.open))
        yield line
        if self.open and self.content is not None:
            if isinstance(self.content, (list, tuple)):
                yield Group(*self.content)
            else:
                yield self.content
