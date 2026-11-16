"""Navigation group composite: label + nav items."""

from __future__ import annotations

from rich.console import Console, ConsoleOptions, Group, RenderResult

from downcroc.cli.design.primitives.nav import NavItem
from downcroc.cli.design.primitives.spacer import spacer
from downcroc.cli.design.primitives.text import label
from downcroc.cli.design.theme import Theme


class NavGroup:
    """A labeled group of navigation items."""

    def __init__(
        self,
        title: str,
        items: list[tuple[str, dict]],
        theme: Theme,
        *,
        width: int = 40,
    ) -> None:
        self.title = title
        self.items = items
        self.theme = theme
        self.width = width

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        parts: list[object] = [
            label(self.title, self.theme),
            spacer(1, theme=self.theme),
        ]
        for text, opts in self.items:
            parts.append(
                NavItem(
                    text,
                    self.theme,
                    icon=str(opts.get("icon", "")),
                    active=bool(opts.get("active", False)),
                    indent=int(opts.get("indent", 0)),
                    badge_text=str(opts.get("badge", "")),
                    width=self.width,
                    state=str(opts.get("state", "default")),
                )
            )
        parts.append(spacer(1, theme=self.theme))
        yield Group(*parts)
