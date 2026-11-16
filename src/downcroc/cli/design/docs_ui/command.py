"""Command dialog/palette components mapped to shadcn Command parts (TUI)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CommandItemSpec:
    id: str
    title: str
    subtitle: str = ""
    shortcut: str = ""
    kind: str = "item"  # page, heading, action
    payload: str = ""


@dataclass(frozen=True)
class CommandGroupSpec:
    label: str
    items: tuple[CommandItemSpec, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CommandPaletteSpec:
    title: str = "Command Palette"
    placeholder: str = "Search pages, headings, actions..."
    groups: tuple[CommandGroupSpec, ...] = field(default_factory=tuple)
    empty_text: str = "No results"


def flatten_groups(
    groups: list[CommandGroupSpec],
) -> list[tuple[str, CommandItemSpec | None]]:
    out: list[tuple[str, CommandItemSpec | None]] = []
    for group in groups:
        out.append((group.label, None))
        for item in group.items:
            out.append((group.label, item))
    return out
