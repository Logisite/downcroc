"""Previous/next pager composite for docs navigation."""

from __future__ import annotations

from rich.columns import Columns
from rich.console import Console, ConsoleOptions, RenderResult
from rich.panel import Panel
from rich.text import Text

from downcroc.cli.design.primitives.spacer import spacer
from downcroc.cli.design.theme import Theme


class Pager:
    """Previous/next navigation block (structural, render states)."""

    def __init__(
        self,
        theme: Theme,
        *,
        prev_label: str = "",
        prev_target: str = "",
        next_label: str = "",
        next_target: str = "",
        width: int = 72,
        prev_state: str = "default",
        next_state: str = "default",
    ) -> None:
        self.theme = theme
        self.prev_label = prev_label
        self.prev_target = prev_target
        self.next_label = next_label
        self.next_target = next_target
        self.width = width
        self.prev_state = prev_state
        self.next_state = next_state

    def _block(
        self, kind: str, label: str, target: str, state: str, align: str
    ) -> Panel:
        t = self.theme
        if not label:
            body = Text(" ", style=t.style("fg_faint"))
            return Panel(
                body,
                border_style=t.style("border_hairline"),
                width=(self.width // 2) - 1,
            )
        active = state in {"hover", "focus", "active"}
        border = (
            "border_focus"
            if state == "focus"
            else "accent"
            if active
            else "border_subtle"
        )
        title_tone = "accent_strong" if active else "fg_muted"
        body_tone = "fg_primary" if active else "fg_secondary"
        hint = "← Previous" if kind == "prev" else "Next →"
        content = Text(justify=align)
        content.append(f"{hint}\n", style=t.style(title_tone, bold=True))
        content.append(label, style=t.style(body_tone, bold=active))
        if target:
            content.append(f"\n{target}", style=t.style("fg_faint"))
        return Panel(
            content,
            border_style=t.style(border),
            padding=(0, 1),
            width=max((self.width // 2) - 1, 20),
        )

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        w = min(self.width, options.max_width)
        self.width = w
        left = self._block(
            "prev", self.prev_label, self.prev_target, self.prev_state, "left"
        )
        right = self._block(
            "next", self.next_label, self.next_target, self.next_state, "right"
        )
        yield Columns([left, right], expand=True, equal=True)
        yield spacer(1, theme=self.theme)
