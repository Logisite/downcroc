"""Button atom primitive (visual states)."""

from __future__ import annotations

from rich.console import Console, ConsoleOptions, RenderResult
from rich.text import Text

from downcroc.cli.design.theme import Theme


class Button:
    """A visual button atom. Interaction behavior is deferred to Phase 2."""

    def __init__(
        self,
        label: str,
        theme: Theme,
        *,
        variant: str = "secondary",
        state: str = "default",
        icon: str = "",
    ) -> None:
        self.label = label
        self.theme = theme
        self.variant = variant
        self.state = state
        self.icon = icon

    def _styles(self) -> tuple[str, str, bool]:
        theme = self.theme
        variant = self.variant
        state = self.state
        bold = True

        if variant == "primary":
            fg, bg = theme.accent_fg, theme.accent
            if state == "hover":
                bg = theme.accent_strong
            elif state == "pressed":
                bg = theme.accent_dim
            elif state == "focus":
                bg = theme.accent
            elif state == "disabled":
                fg, bg, bold = theme.fg_muted, theme.bg_raised, False
        elif variant == "danger":
            fg, bg = theme.accent_fg, theme.danger
            if state == "hover":
                bg = "#ff6b64"
            elif state == "pressed":
                bg = "#c93c37"
            elif state == "focus":
                bg = theme.danger
            elif state == "disabled":
                fg, bg, bold = theme.fg_muted, theme.bg_raised, False
        elif variant == "ghost":
            fg, bg = theme.fg_secondary, theme.bg_page
            if state == "hover":
                fg, bg = theme.fg_primary, theme.bg_hover
            elif state == "pressed":
                fg, bg = theme.fg_primary, theme.bg_active
            elif state == "focus":
                fg, bg = theme.accent_strong, theme.bg_hover
            elif state == "disabled":
                fg, bold = theme.fg_faint, False
        else:  # secondary
            fg, bg = theme.fg_primary, theme.bg_raised
            if state == "hover":
                bg = theme.bg_hover
            elif state == "pressed":
                bg = theme.bg_active
            elif state == "focus":
                fg = theme.accent_strong
            elif state == "disabled":
                fg, bg, bold = theme.fg_faint, theme.bg_panel, False

        if state == "focus" and variant in {"primary", "danger"}:
            fg = theme.accent_fg
        return fg, bg, bold

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        fg, bg, bold = self._styles()
        text = Text()
        pad_style = f"{fg} on {bg}"
        text.append(" ", style=pad_style)
        if self.state == "focus":
            text.append("▏", style=f"{self.theme.border_focus} on {bg}")
        if self.icon:
            text.append(f"{self.icon} ", style=("bold " if bold else "") + pad_style)
        text.append(self.label, style=("bold " if bold else "") + pad_style)
        text.append(" ", style=pad_style)
        yield text
