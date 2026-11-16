"""Tag list primitive."""

from __future__ import annotations

from rich.console import Console, ConsoleOptions, RenderResult
from rich.text import Text

from downcroc.cli.design.theme import Theme


class TagList:
    """A row of meta tags/chips."""

    def __init__(
        self, tags: list[str], theme: Theme, *, tone: str = "bg_raised"
    ) -> None:
        self.tags = tags
        self.theme = theme
        self.tone = tone

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        theme = self.theme
        line = Text()
        for index, tag in enumerate(self.tags):
            if index:
                line.append(" ")
            line.append(f" {tag} ", style=theme.style("fg_secondary", on=self.tone))
        yield line
