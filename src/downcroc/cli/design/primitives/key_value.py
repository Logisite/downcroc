"""Key-value and definition row primitives."""

from __future__ import annotations

from rich.console import Console, ConsoleOptions, RenderResult
from rich.table import Table
from rich.text import Text

from downcroc.cli.design.theme import Theme


class KeyValue:
    """Aligned key/value rows."""

    def __init__(
        self,
        items: list[tuple[str, str]],
        theme: Theme,
        *,
        key_width: int | None = None,
        compact: bool = False,
        divider: bool = False,
    ) -> None:
        self.items = items
        self.theme = theme
        self.key_width = key_width
        self.compact = compact
        self.divider = divider

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        theme = self.theme
        pad = (0, 1) if self.compact else (0, 2)
        grid = Table.grid(padding=pad)
        grid.add_column(
            width=self.key_width,
            style=theme.style("fg_muted"),
            no_wrap=True,
        )
        grid.add_column(style=theme.style("fg_secondary"))

        def divider_line() -> Text:
            # Continuous rule: span approximate rendered grid width.
            key_w = self.key_width or max((len(k) for k, _ in self.items), default=8)
            val_w = max((len(v) for _, v in self.items), default=8)
            gap = pad[1]
            width = max(min(key_w + gap + val_w, options.max_width), 16)
            return Text("─" * width, style=theme.style("border_hairline"))

        for index, (key, value) in enumerate(self.items):
            grid.add_row(key, value)
            if self.divider and index < len(self.items) - 1:
                yield grid
                yield divider_line()
                grid = Table.grid(padding=pad)
                grid.add_column(
                    width=self.key_width,
                    style=theme.style("fg_muted"),
                    no_wrap=True,
                )
                grid.add_column(style=theme.style("fg_secondary"))
        yield grid
