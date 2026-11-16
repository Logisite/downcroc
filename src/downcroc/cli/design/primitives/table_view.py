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
        col_widths: list[int | None] | None = None,
        no_wrap: list[bool] | None = None,
        compact: bool = False,
        zebra: bool = True,
        empty_text: str = "No rows",
        show_header_on_empty: bool = False,
    ) -> None:
        self.headers = headers
        self.rows = rows
        self.theme = theme
        self.width = width
        self.align = align or []
        self.col_widths = col_widths or []
        self.no_wrap = no_wrap or []
        self.compact = compact
        self.zebra = zebra
        self.empty_text = empty_text
        self.show_header_on_empty = show_header_on_empty

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        theme = self.theme
        if not self.rows and not self.show_header_on_empty:
            yield Text(self.empty_text, style=theme.style("fg_faint"))
            return
        padding = (0, 1)
        row_styles = [Style(color=theme.fg_secondary)]
        if self.zebra:
            row_styles.append(Style(color=theme.fg_secondary, bgcolor=theme.bg_panel))
        table = Table(
            box=box.SQUARE,
            show_edge=True,
            pad_edge=True,
            show_lines=True,
            expand=bool(self.width),
            width=self.width,
            padding=padding,
            header_style=Style(
                color=theme.fg_primary, bold=True, bgcolor=theme.bg_raised
            ),
            border_style=Style(color=theme.border_strong),
            row_styles=row_styles,
        )
        for index, header in enumerate(self.headers):
            justify = self.align[index] if index < len(self.align) else "left"
            col_width = self.col_widths[index] if index < len(self.col_widths) else None
            col_no_wrap = (
                self.no_wrap[index] if index < len(self.no_wrap) else self.compact
            )
            overflow = "ellipsis" if col_no_wrap else "fold"
            table.add_column(
                header,
                justify=justify,
                width=col_width,
                overflow=overflow,
                no_wrap=col_no_wrap,
            )
        if not self.rows and self.show_header_on_empty:
            if self.headers:
                empty_row = [self.empty_text] + [""] * (len(self.headers) - 1)
                table.add_row(*empty_row)
            else:
                table.caption = self.empty_text
                table.caption_style = Style(color=theme.fg_faint)
        for row in self.rows:
            table.add_row(*row)
        yield table
