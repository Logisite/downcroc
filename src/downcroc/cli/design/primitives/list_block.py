"""List primitives: bullet, ordered, and task lists."""

from __future__ import annotations

from rich.console import Console, ConsoleOptions, Group, RenderResult
from rich.text import Text

from downcroc.cli.design.theme import Theme


class ListItem:
    """A single list item with marker, indentation, and optional task state."""

    def __init__(
        self,
        text: str,
        theme: Theme,
        *,
        marker: str = "•",
        level: int = 0,
        checked: bool | None = None,
    ) -> None:
        self.text = text
        self.theme = theme
        self.marker = marker
        self.level = level
        self.checked = checked

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        theme = self.theme
        indent = "  " * max(self.level, 0)
        if self.checked is True:
            mark = Text("☑", style=theme.style("success"))
            marker_plain = "☑"
        elif self.checked is False:
            mark = Text("☐", style=theme.style("fg_muted"))
            marker_plain = "☐"
        else:
            mark = Text(self.marker, style=theme.style("accent"))
            marker_plain = self.marker
        marker_width = max(len(marker_plain), 2)
        body = Text(self.text, style=theme.style("fg_secondary"))
        wrap_width = max(options.max_width - len(indent) - marker_width - 1, 8)
        lines = list(body.wrap(console, wrap_width, overflow="fold")) or [Text("")]
        first = Text(indent)
        padded_mark = Text(marker_plain.ljust(marker_width), style=mark.style)
        first.append_text(padded_mark)
        first.append(" ")
        first.append_text(lines[0])
        yield first
        cont = " " * (len(indent) + marker_width + 1)
        for extra in lines[1:]:
            line = Text(cont)
            line.append_text(extra)
            yield line


class ListBlock:
    """A list of items: ul, ol, or task list."""

    def __init__(
        self,
        items: list[str] | list[tuple[object, ...]],
        theme: Theme,
        *,
        ordered: bool = False,
        task: bool = False,
        start: int = 1,
    ) -> None:
        self.items = items
        self.theme = theme
        self.ordered = ordered
        self.task = task
        self.start = start

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        rendered = []
        for index, item in enumerate(self.items):
            if isinstance(item, tuple):
                text = str(item[0])
                level = int(item[1]) if len(item) > 1 else 0
                checked = item[2] if len(item) > 2 else None
            else:
                text = str(item)
                level = 0
                checked = False if self.task else None
            if self.ordered:
                marker = f"{self.start + index}."
            else:
                marker = "•"
            rendered.append(
                ListItem(text, self.theme, marker=marker, level=level, checked=checked)
            )
        yield Group(*rendered)
