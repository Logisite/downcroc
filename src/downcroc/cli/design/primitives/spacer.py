"""Spacer primitive: explicit vertical gaps."""

from __future__ import annotations

from rich.text import Text


def spacer(lines: int = 1) -> Text:
    """Vertical space as empty lines."""
    return Text("\n" * max(lines - 1, 0))
