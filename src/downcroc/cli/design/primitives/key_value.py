"""Key-value and definition row primitives."""

from __future__ import annotations

from rich.console import Console, ConsoleOptions, RenderResult
from rich.table import Table

from downcroc.cli.design.theme import Theme


class KeyValue:
    """Aligned key/value rows."""

    def __init__(
        self,
        items: list[tuple[str, str]],
        theme: Theme,
        *,
        key_width: int | None = None,
    ) -> None:
        self.items = items
        self.theme = theme
        self.key_width = key_width

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        theme = self.theme
        grid = Table.grid(padding=(0, 2))
        grid.add_column(
            width=self.key_width,
            style=theme.style("fg_muted"),
            no_wrap=True,
        )
        grid.add_column(style=theme.style("fg_secondary"))
        for key, value in self.items:
            grid.add_row(key, value)
        yield grid
