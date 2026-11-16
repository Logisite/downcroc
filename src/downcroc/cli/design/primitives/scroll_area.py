"""ScrollArea primitive mapping (Textual-aligned container hint)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScrollAreaSpec:
    """Describes a scrollable region; actual scrolling is provided by Textual containers."""

    orientation: str = "vertical"
    show_scrollbar: bool = True
    id: str = ""
