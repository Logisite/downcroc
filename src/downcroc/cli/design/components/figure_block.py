"""Figure composite: content + caption assembled from primitives."""

from __future__ import annotations

from rich.console import Console, ConsoleOptions, Group, RenderResult

from downcroc.cli.design.primitives.figure import Figure
from downcroc.cli.design.primitives.spacer import spacer
from downcroc.cli.design.theme import Theme


class FigureBlock:
    """Figure composition wrapper for gallery/component assembly."""

    def __init__(
        self, content: object, caption: str, theme: Theme, *, width: int | None = None
    ) -> None:
        self.content = content
        self.caption = caption
        self.theme = theme
        self.width = width

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        yield Group(
            Figure(self.content, self.theme, caption=self.caption),
            spacer(1, theme=self.theme),
        )
