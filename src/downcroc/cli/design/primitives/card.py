"""Card brick: a rounded card painted with background stepping."""

from __future__ import annotations

from rich.console import Console, ConsoleOptions, RenderResult
from rich.style import Style
from rich.text import Text

from downcroc.cli.design.paint.canvas import CellCanvas
from downcroc.cli.design.theme import Theme


class Card:
    """A card painted from tokens, never from stock Panel chrome.

    The dark-web look is background stepping, not outlines: by default a card
    is a borderless rectangle of stepped fill that reads from the bg change
    plus padding. ``border="hairline"`` adds a barely-visible alpha hairline;
    a full glyph border stays reserved for code panels and modals.

    Render is pure f(props, theme).
    """

    def __init__(
        self,
        title: str,
        body: str,
        theme: Theme,
        *,
        width: int = 40,
        min_height: int = 4,
        fill: str = "bg_panel",
        border: str | None = None,
    ) -> None:
        self.title = title
        self.body = body
        self.theme = theme
        self.width = width
        self.min_height = min_height
        self.fill = fill
        self.border = border

    def _body_lines(self, inner_width: int) -> list[str]:
        words = self.body.split()
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if len(candidate) > inner_width and current:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
        return lines

    def _paint_border(self, canvas: CellCanvas) -> None:
        if self.border == "hairline":
            canvas.rounded_rect(
                self.theme.style("border_hairline"),
                fill=self.theme.bg(self.fill),
            )
        else:
            canvas.fill(self.theme.bg(self.fill))

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        width = min(self.width, options.max_width)
        inset = 2 if self.border else 1
        inner_width = width - inset * 2 - 1
        body_lines = self._body_lines(inner_width)
        frame = 2 if self.border else 0
        height = max(self.min_height, frame + len(body_lines) + 3)
        canvas = CellCanvas(width, height)
        self._paint_border(canvas)
        title_row = 1
        panel = self.theme.bg(self.fill)
        title_style = self.theme.style("fg_primary", bold=True) + panel
        title = Text(self.title, style=title_style)
        for offset, glyph in enumerate(title.plain):
            canvas.set(inset + offset, title_row, glyph, title.style or Style())
        body_style = self.theme.style("fg_secondary") + panel
        for row, line in enumerate(body_lines):
            body = Text(line, style=body_style)
            for offset, glyph in enumerate(line):
                canvas.set(
                    inset + offset, title_row + 2 + row, glyph, body.style or Style()
                )
        yield from canvas.segments()

    def __rich_measure__(
        self, console: Console, options: ConsoleOptions
    ) -> tuple[int, int]:
        return min(20, self.width), self.width
