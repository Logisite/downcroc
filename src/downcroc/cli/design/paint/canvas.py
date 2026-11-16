"""CellCanvas: a tiny cell-buffer painter.

Bricks paint into a CellCanvas and hand it to Rich as segments. This is the
background-fill layer: rectangles, hairlines, and rounded cards built from
background colors and box-drawing characters, not ASCII art.
"""

from __future__ import annotations

from collections.abc import Iterator

from rich.console import Console, ConsoleOptions, RenderResult
from rich.segment import Segment
from rich.style import Style

from downcroc.cli.design.theme import Theme

_EMPTY = " "


class CellCanvas:
    """A width x height grid of (glyph, style) cells."""

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self._cells: list[list[tuple[str, Style]]] = [
            [(_EMPTY, Style())] * 0 for _ in range(0)
        ]
        self._grid: list[list[tuple[str, Style]]] = [
            [(_EMPTY, Style()) for _ in range(width)] for _ in range(height)
        ]

    def set(self, x: int, y: int, glyph: str, style: Style) -> None:
        """Paint one cell, ignoring out-of-bounds writes."""
        if 0 <= x < self.width and 0 <= y < self.height:
            self._grid[y][x] = (glyph, style)

    def fill(self, style: Style) -> None:
        """Fill every cell with a background style."""
        blank = (_EMPTY, style)
        for row in self._grid:
            for x in range(self.width):
                row[x] = blank

    def fill_rect(self, x: int, y: int, w: int, h: int, style: Style) -> None:
        """Fill a rectangle with a style, clipped to bounds."""
        for row in range(y, y + h):
            for col in range(x, x + w):
                self.set(col, row, _EMPTY, style)

    def hline(self, x: int, y: int, width: int, glyph: str, style: Style) -> None:
        for col in range(x, x + width):
            self.set(col, y, glyph, style)

    def vline(self, x: int, y: int, height: int, glyph: str, style: Style) -> None:
        for row in range(y, y + height):
            self.set(x, row, glyph, style)

    def rounded_rect(self, style: Style, *, fill: Style | None = None) -> None:
        """Draw a rounded hairline rect covering the whole canvas.

        ``fill`` paints the interior background; border cells carry the fill
        as their own background so the hairline sits flush on the card.
        """
        right = self.width - 1
        bottom = self.height - 1
        if right < 1 or bottom < 1:
            return
        border_style = style + fill if fill is not None else style
        if fill is not None:
            self.fill_rect(1, 1, right - 1, bottom - 1, fill)
        self.set(0, 0, "╭", border_style)
        self.set(right, 0, "╮", border_style)
        self.set(0, bottom, "╰", border_style)
        self.set(right, bottom, "╯", border_style)
        self.hline(1, 0, right - 1, "─", border_style)
        self.hline(1, bottom, right - 1, "─", border_style)
        for row in range(1, bottom):
            self.set(0, row, "│", border_style)
            self.set(right, row, "│", border_style)

    def segments(self) -> Iterator[Segment]:
        for row in self._grid:
            run_text = ""
            run_style: Style | None = None
            for glyph, style in row:
                if run_style is not None and style == run_style:
                    run_text += glyph
                    continue
                if run_text:
                    assert run_style is not None
                    yield Segment(run_text, run_style)
                run_text = glyph
                run_style = style
            if run_text:
                assert run_style is not None
                yield Segment(run_text, run_style)
            yield Segment("\n")


class CanvasRenderable:
    """Wrap a painted CellCanvas as a Rich renderable."""

    def __init__(self, canvas: CellCanvas) -> None:
        self._canvas = canvas

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        yield from self._canvas.segments()

    def __rich_measure__(
        self, console: Console, options: ConsoleOptions
    ) -> tuple[int, int]:
        return self._canvas.width, self._canvas.width


def paint_card(
    width: int, height: int, theme: Theme, *, fill: str = "bg_panel"
) -> CellCanvas:
    """Paint a rounded card: hairline border on the page, stepped bg fill."""
    canvas = CellCanvas(width, height)
    canvas.fill(theme.bg("bg_page"))
    canvas.rounded_rect(
        theme.style("border_hairline"),
        fill=theme.bg(fill),
    )
    return canvas
