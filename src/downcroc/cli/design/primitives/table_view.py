"""Table primitive: header band and zebra rows, theme-driven."""

from __future__ import annotations

from rich import box
from rich.console import Console, ConsoleOptions, RenderResult
from rich.style import Style
from rich.table import Table
from rich.text import Text

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
        align: list[str] | None = None,
        compact: bool = False,
        zebra: bool = True,
        empty_text: str = "No rows",
    ) -> None:
        self.headers = headers
        self.rows = rows
        self.theme = theme
        self.width = width
        self.align = align or []
        self.compact = compact
        self.zebra = zebra
        self.empty_text = empty_text

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        theme = self.theme
        if not self.rows:
            yield Text(self.empty_text, style=theme.style("fg_faint"))
            return
        padding = (0, 0) if self.compact else (0, 1)
        row_styles = [Style(color=theme.fg_secondary)]
        if self.zebra:
            row_styles.append(Style(color=theme.fg_secondary, bgcolor=theme.bg_panel))
        table = Table(
            box=box.SIMPLE_HEAD,
            show_edge=False,
            pad_edge=False,
            expand=bool(self.width),
            width=self.width,
            padding=padding,
            header_style=Style(
                color=theme.fg_primary, bold=True, bgcolor=theme.bg_raised
            ),
            border_style=Style(color=theme.border_subtle),
            row_styles=row_styles,
        )
        for index, header in enumerate(self.headers):
            justify = "left"
            if index < len(self.align):
                justify = self.align[index]
            overflow = "ellipsis" if not self.compact else "fold"
            table.add_column(
                header, justify=justify, overflow=overflow, no_wrap=self.compact
            )
        for row in self.rows:
            table.add_row(*row)
        yield table
