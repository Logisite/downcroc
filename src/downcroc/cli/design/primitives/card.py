"""Card brick: a surface painted with background stepping."""

from __future__ import annotations

from rich.console import Console, ConsoleOptions, RenderResult
from rich.text import Text

from downcroc.cli.design.paint.canvas import CellCanvas
from downcroc.cli.design.theme import Theme


class Card:
    """A card surface: stepped fill by default, optional hairline border.

    Render is pure f(props, theme).
    """

    def __init__(
        self,
        title: str,
        body: str,
        theme: Theme,
        *,
        width: int = 40,
        fill: str = "bg_panel",
        border: str | None = None,
    ) -> None:
        self.title = title
        self.body = body
        self.theme = theme
        self.width = width
        self.fill = fill
        self.border = border

    def _wrap(self, text: str, width: int) -> list[str]:
        words = text.split()
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if len(candidate) > width and current:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
        return lines or [""]

    def _render_plain(self, width: int) -> RenderResult:
        theme = self.theme
        panel = theme.bg(self.fill)
        pad = theme.space_1
        inner = max(width - (pad * 2), 10)
        yield Text(" " * width, style=panel)
        yield Text(
            ((" " * pad) + self.title).ljust(width),
            style=theme.style("fg_primary", bold=True) + panel,
        )
        yield Text(" " * width, style=panel)
        for line in self._wrap(self.body, inner):
            yield Text(
                ((" " * pad) + line).ljust(width),
                style=theme.style("fg_secondary") + panel,
            )
        yield Text(" " * width, style=panel)

    def _render_hairline(self, width: int) -> RenderResult:
        theme = self.theme
        panel = theme.bg(self.fill)
        pad = theme.space_2
        inner = max(width - (pad * 2), 10)
        body_lines = self._wrap(self.body, inner)
        height = 4 + len(body_lines)
        canvas = CellCanvas(width, height)
        canvas.rounded_rect(theme.style("border_hairline"), fill=panel)
        # write text into canvas
        title_style = theme.style("fg_primary", bold=True) + panel
        for i, ch in enumerate(self.title[: inner + 1]):
            canvas.set(pad + i, 1, ch, title_style)
        body_style = theme.style("fg_secondary") + panel
        for r, line in enumerate(body_lines):
            for i, ch in enumerate(line):
                canvas.set(pad + i, 3 + r, ch, body_style)
        yield from canvas.segments()

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        width = min(self.width, options.max_width)
        if self.border == "hairline":
            yield from self._render_hairline(width)
        else:
            yield from self._render_plain(width)

    def __rich_measure__(
        self, console: Console, options: ConsoleOptions
    ) -> tuple[int, int]:
        return min(20, self.width), self.width
