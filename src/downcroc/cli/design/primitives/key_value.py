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
        stacked: bool = False,
        width: int | None = None,
    ) -> None:
        self.items = items
        self.theme = theme
        self.key_width = key_width
        self.compact = compact
        self.divider = divider
        self.stacked = stacked
        self.width = width

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        theme = self.theme
        pad = (0, 1) if self.compact else (0, 2)
        target_width = min(self.width or options.max_width, options.max_width)

        if self.stacked:
            for index, (key, value) in enumerate(self.items):
                yield Text(key, style=theme.style("fg_muted"))
                yield Text(f"  {value}", style=theme.style("fg_secondary"))
                if self.divider and index < len(self.items) - 1:
                    width = max(min(target_width, 72), 20)
                    yield Text("─" * width, style=theme.style("border_hairline"))
                elif index < len(self.items) - 1 and not self.compact:
                    yield Text("")
            return

        grid = Table.grid(padding=pad)
        grid.add_column(
            width=self.key_width,
            style=theme.style("fg_muted"),
            no_wrap=True,
        )
        grid.add_column(style=theme.style("fg_secondary"))

        def divider_line() -> Text:
            # Continuous rule across available width.
            width = max(min(target_width, 72), 20)
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
