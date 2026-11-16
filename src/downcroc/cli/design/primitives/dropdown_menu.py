"""Dropdown/Popover/Command menu primitives (shadcn mappings, render-state)."""

from __future__ import annotations

from dataclasses import dataclass

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.text import Text

from downcroc.cli.design.theme import DEFAULT, Theme


@dataclass(frozen=True)
class MenuItem:
    label: str
    value: str = ""
    shortcut: str = ""
    disabled: bool = False
    kind: str = "item"  # item, separator, label


def render_menu(
    items: list[MenuItem],
    theme: Theme = DEFAULT,
    *,
    title: str = "",
    width: int = 40,
) -> Panel:
    rows: list[RenderableType] = []
    if title:
        rows.append(Text(title, style=theme.style("fg_muted")))
        rows.append(Text(""))
    for item in items:
        if item.kind == "separator":
            rows.append(
                Text("─" * max(width - 4, 8), style=theme.style("border_subtle"))
            )
            continue
        if item.kind == "label":
            rows.append(Text(item.label, style=theme.style("fg_faint", bold=True)))
            continue
        style = (
            theme.style("fg_faint") if item.disabled else theme.style("fg_secondary")
        )
        line = Text(f"  {item.label}", style=style)
        if item.shortcut:
            pad = max(width - len(line.plain) - len(item.shortcut) - 4, 1)
            line.append(" " * pad)
            line.append(item.shortcut, style=theme.style("fg_faint"))
        rows.append(line)
    return Panel(
        Group(*rows),
        border_style=theme.style("border_subtle"),
        width=width,
        padding=(0, 1),
    )


render_dropdown = render_menu
render_popover = render_menu
render_command_menu = render_menu
