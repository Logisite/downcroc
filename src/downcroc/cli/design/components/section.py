"""Section composite: header + body content, built from primitives."""

from __future__ import annotations

from rich.console import Console, ConsoleOptions, Group, RenderResult

from downcroc.cli.design.primitives.section_header import SectionHeader
from downcroc.cli.design.primitives.spacer import spacer
from downcroc.cli.design.theme import Theme


class Section:
    """A titled section grouping content primitives."""

    def __init__(
        self,
        title: str,
        content: object | list[object],
        theme: Theme,
        *,
        meta: str = "",
    ) -> None:
        self.title = title
        self.content = content if isinstance(content, list) else [content]
        self.theme = theme
        self.meta = meta

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        parts: list[object] = [SectionHeader(self.title, self.theme, meta=self.meta)]
        parts.extend(self.content)
        parts.append(spacer(1, theme=self.theme))
        yield Group(*parts)
