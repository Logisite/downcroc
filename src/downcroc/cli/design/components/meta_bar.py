"""Meta bar composite for docs/page metadata rows."""

from __future__ import annotations

from rich.console import Console, ConsoleOptions, Group, RenderResult
from rich.text import Text

from downcroc.cli.design.primitives.spacer import spacer
from downcroc.cli.design.theme import Theme


class MetaBar:
    """Compact horizontal meta row (label/value pairs) for docs headers."""

    def __init__(
        self,
        items: list[tuple[str, str]],
        theme: Theme,
        *,
        separator: str = "  •  ",
    ) -> None:
        self.items = items
        self.theme = theme
        self.separator = separator

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        row = Text()
        for i, (key, value) in enumerate(self.items):
            if i:
                row.append(self.separator, style=self.theme.style("fg_faint"))
            row.append(f"{key}: ", style=self.theme.style("fg_muted"))
            row.append(value, style=self.theme.style("fg_secondary"))
        yield Group(row, spacer(1, theme=self.theme))
