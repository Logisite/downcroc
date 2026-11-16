"""Blockquote primitive: quoted content with a left bar."""

from __future__ import annotations

from rich.console import Console, ConsoleOptions, RenderResult
from rich.text import Text

from downcroc.cli.design.theme import Theme


class Blockquote:
    """A blockquote: left accent bar and muted body."""

    def __init__(
        self,
        text: str,
        theme: Theme,
        *,
        cite: str | None = None,
        width: int | None = None,
    ) -> None:
        self.text = text
        self.theme = theme
        self.cite = cite
        self.width = width

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        theme = self.theme
        inset = theme.space_2
        width = max((self.width or options.max_width) - inset, 10)
        body = Text(self.text or "", style=theme.style("fg_muted"))
        for line in body.wrap(console, width, overflow="fold"):
            yield Text.assemble(Text("▎ ", style=theme.style("border_strong")), line)
        if self.cite:
            yield Text(f"{' ' * inset}— {self.cite}", style=theme.style("fg_faint"))
        yield Text("")
