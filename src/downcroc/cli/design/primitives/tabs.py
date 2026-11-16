"""Tabs primitive/composition (shadcn Tabs mapping, render-state)."""

from __future__ import annotations

from rich.console import Console, ConsoleOptions, RenderResult
from rich.text import Text

from downcroc.cli.design.theme import DEFAULT, Theme


class Tabs:
    """Tab strip + active panel content (static/render-state mapping)."""

    def __init__(
        self,
        tabs: list[tuple[str, object]],
        *,
        active: str | int = 0,
        theme: Theme = DEFAULT,
    ) -> None:
        self.tabs = tabs
        self.active = active
        self.theme = theme

    def _active_index(self) -> int:
        if isinstance(self.active, int):
            return max(0, min(self.active, len(self.tabs) - 1)) if self.tabs else -1
        for i, (name, _) in enumerate(self.tabs):
            if name == self.active:
                return i
        return 0 if self.tabs else -1

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        active = self._active_index()
        strip = Text()
        for i, (name, _) in enumerate(self.tabs):
            if i:
                strip.append("  ", style=self.theme.style("bg_page"))
            if i == active:
                strip.append(
                    f" {name} ",
                    style=self.theme.style(
                        "accent_strong", on="bg_selected", bold=True
                    ),
                )
            else:
                strip.append(
                    f" {name} ", style=self.theme.style("fg_muted", on="bg_panel")
                )
        yield strip
        yield Text("")
        if 0 <= active < len(self.tabs):
            yield self.tabs[active][1]
            yield Text("")
