"""Generic panel/surface primitive."""

from __future__ import annotations

from rich.console import Console, ConsoleOptions, RenderResult
from rich.text import Text

from downcroc.cli.design.theme import Theme


class Panel:
    """A simple filled surface block (no title chrome)."""

    def __init__(
        self,
        body: str,
        theme: Theme,
        *,
        width: int | None = None,
        fill: str = "bg_panel",
        padding: int | None = None,
    ) -> None:
        self.body = body
        self.theme = theme
        self.width = width
        self.fill = fill
        self.padding = padding

    def _wrap(self, text: str, width: int) -> list[str]:
        if not text:
            return [""]
        lines: list[str] = []
        for para in text.splitlines() or [""]:
            words = para.split()
            if not words:
                lines.append("")
                continue
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
        return lines

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        theme = self.theme
        width = min(self.width or options.max_width, options.max_width)
        pad = theme.space_1 if self.padding is None else max(int(self.padding), 0)
        inner = max(width - pad * 2, 8)
        panel = theme.bg(self.fill)
        blank = Text(" " * width, style=panel)
        for _ in range(pad):
            yield blank
        for line in self._wrap(self.body, inner):
            yield Text(
                (" " * pad + line).ljust(width),
                style=theme.style("fg_secondary") + panel,
            )
        for _ in range(pad):
            yield blank
