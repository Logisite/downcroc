"""Table primitive: header band and zebra rows, theme-driven."""

from __future__ import annotations

from rich import box
from rich.console import Console, ConsoleOptions, RenderResult
from rich.style import Style
from rich.table import Table

from downcroc.cli.design.theme import Theme


class TableView:
    """A styled data table."""

    def __init__(
        self,
        headers: list[str],
        rows: list[list[str]],
        theme: Theme,
        *,
        width: int | None = None,
    ) -> None:
        self.headers = headers
        self.rows = rows
        self.theme = theme
        self.width = width

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        theme = self.theme
        table = Table(
            box=box.SIMPLE_HEAD,
            show_edge=False,
            pad_edge=False,
            header_style=Style(color=theme.fg_primary, bold=True),
            border_style=Style(color=theme.border_hairline),
            row_styles=[
                Style(color=theme.fg_secondary),
                Style(color=theme.fg_secondary, bgcolor=theme.bg_panel),
            ],
        )
        for header in self.headers:
            table.add_column(header)
        for row in self.rows:
            table.add_row(*row)
        yield table
