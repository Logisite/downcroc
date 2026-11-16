"""Figure primitive with optional caption."""

from __future__ import annotations

from rich.console import Console, ConsoleOptions, Group, RenderResult
from rich.text import Text

from downcroc.cli.design.theme import Theme


class Figure:
    """A content block with an optional caption."""

    def __init__(
        self,
        content: object,
        theme: Theme,
        *,
        caption: str = "",
    ) -> None:
        self.content = content
        self.theme = theme
        self.caption = caption

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        parts: list[object] = [self.content]
        if self.caption:
            parts.append(Text(self.caption, style=self.theme.style("fg_faint")))
        yield Group(*parts)
        yield Text("")
