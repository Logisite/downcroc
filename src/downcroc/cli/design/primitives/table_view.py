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
        rows: list[list[str]] | list[tuple[list[str], bool]],
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
        caption: str = "",
        caption_justify: str = "center",
        title: str = "",
        row_styles: list[str | Style] | None = None,
        show_lines: bool = True,
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
        self.caption = caption
        self.caption_justify = caption_justify
        self.title = title
        self.row_styles = row_styles
        self.show_lines = show_lines

    def _resolve_row_style(self, style: str | Style | None) -> str | Style | None:
        theme = self.theme
        if style is None:
            return None
        if isinstance(style, Style):
            return style
        mapping = {
            "selected": f"{theme.accent_strong} on {theme.bg_selected}",
            "active": f"{theme.accent_strong} on {theme.bg_selected}",
            "hover": f"{theme.fg_primary} on {theme.bg_hover}",
            "focus": f"{theme.accent_strong} on {theme.bg_hover}",
            "success": f"{theme.success} on {theme.success_dim}",
            "warning": f"{theme.warning} on {theme.warning_dim}",
            "danger": f"{theme.danger} on {theme.danger_dim}",
            "muted": f"{theme.fg_muted} on {theme.bg_panel}",
        }
        return mapping.get(style, style)

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        theme = self.theme
        if not self.rows and not self.show_header_on_empty:
            yield Text(self.empty_text, style=theme.style("fg_faint"))
            return
        padding = (0, theme.space_1)
        base_row_styles: list[str | Style] = [Style(color=theme.fg_secondary)]
        if self.zebra:
            base_row_styles.append(
                Style(color=theme.fg_secondary, bgcolor=theme.bg_panel)
            )
        row_styles = self.row_styles if self.row_styles is not None else base_row_styles
        table = Table(
            title=self.title or None,
            caption=self.caption or None,
            box=box.SQUARE,
            show_edge=True,
            pad_edge=True,
            show_lines=self.show_lines,
            expand=bool(self.width),
            width=self.width,
            padding=padding,
            header_style=Style(
                color=theme.fg_primary, bold=True, bgcolor=theme.bg_raised
            ),
            border_style=Style(color=theme.border_strong),
            caption_style=Style(color=theme.fg_faint),
            caption_justify=self.caption_justify,
            title_style=Style(color=theme.fg_secondary, bold=True),
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
                empty_style = Style(
                    color=theme.fg_muted, italic=True, bgcolor=theme.bg_panel
                )
                empty_row = [Text(f"  {self.empty_text}", style=empty_style)]
                empty_row.extend(
                    Text("", style=Style(bgcolor=theme.bg_panel))
                    for _ in range(len(self.headers) - 1)
                )
                table.add_row(*empty_row)
            else:
                table.caption = self.empty_text
                table.caption_style = Style(color=theme.fg_faint)
        for row in self.rows:
            if isinstance(row, dict):
                cells = row.get("cells", [])
                end_section = bool(row.get("end_section", False))
                row_style = self._resolve_row_style(row.get("style"))
                table.add_row(*cells, end_section=end_section, style=row_style)
                continue
            if isinstance(row, tuple):
                if len(row) == 3:
                    cells, end_section, row_style = row
                    table.add_row(
                        *cells,
                        end_section=bool(end_section),
                        style=self._resolve_row_style(row_style),
                    )
                    continue
                if len(row) == 2:
                    first, second = row
                    if (
                        isinstance(second, (str, Style))
                        and not isinstance(first, bool)
                        and isinstance(first, list)
                    ):
                        # (cells, style)
                        table.add_row(*first, style=self._resolve_row_style(second))
                        continue
                    cells, end_section = row
                    table.add_row(*cells, end_section=bool(end_section))
                    continue
            table.add_row(*row)
        yield table
