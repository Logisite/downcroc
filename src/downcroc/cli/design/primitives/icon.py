"""Icon registry and status markers."""

from __future__ import annotations

from rich.text import Text

from downcroc.cli.design.theme import Theme

# Nerd Font friendly defaults with simple fallbacks implied by choice.
ICONS: dict[str, str] = {
    "account": "󰀄",
    "inbox": "󰇮",
    "sent": "󰒊",
    "folder": "󰉋",
    "mail": "󰇮",
    "search": "󰍉",
    "settings": "󰒓",
    "info": "󰋽",
    "success": "󰄬",
    "warning": "󰀪",
    "danger": "󰅚",
    "dot": "●",
    "bullet": "•",
    "chevron": "›",
    "check": "✓",
    "pending": "◌",
    "empty": "∅",
}


def resolve_icon(name: str) -> str:
    """Resolve a known icon role to a glyph, or return the input as-is."""
    return ICONS.get(name, name)


def icon(name: str, theme: Theme, *, tone: str = "fg_muted") -> Text:
    """Return a themed glyph by role/name."""
    return Text(resolve_icon(name), style=theme.style(tone))


def status_dot(theme: Theme, *, tone: str = "info") -> Text:
    """A small semantic status marker."""
    return Text("●", style=theme.style(tone))
