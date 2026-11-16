"""Breadcrumb bar composite for docs headers/navigation context."""

from __future__ import annotations

from rich.console import Console, ConsoleOptions, Group, RenderResult

from downcroc.cli.design.primitives.spacer import spacer
from downcroc.cli.design.primitives.text import breadcrumb, label
from downcroc.cli.design.theme import Theme


class BreadcrumbBar:
    """Labeled breadcrumb row composed from primitives."""

    def __init__(
        self,
        items: list[str] | list[tuple[str, str]],
        theme: Theme,
        *,
        title: str = "",
        separator: str = " › ",
    ) -> None:
        self.items = items
        self.theme = theme
        self.title = title
        self.separator = separator

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        parts: list[object] = []
        if self.title:
            parts.append(label(self.title, self.theme))
        parts.append(breadcrumb(self.items, self.theme, separator=self.separator))
        parts.append(spacer(1, theme=self.theme))
        yield Group(*parts)
