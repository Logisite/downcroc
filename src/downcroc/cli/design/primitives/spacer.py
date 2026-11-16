"""Spacer primitive: explicit vertical gaps."""

from __future__ import annotations

from rich.text import Text

from downcroc.cli.design.theme import Theme


def spacer(
    lines: int = 1, *, theme: Theme | None = None, size: str | None = None
) -> Text:
    """Vertical space as empty lines.

    `size` can map to theme spacing tokens (space_1..space_8) when theme is provided.
    """
    if size and theme is not None:
        token = f"space_{size}" if not size.startswith("space_") else size
        lines = int(getattr(theme, token, lines))
    count = max(int(lines), 0)
    if count <= 0:
        return Text("")
    return Text("\n" * max(count - 1, 0))
