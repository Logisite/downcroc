"""Topbar components: breadcrumbs, triggers, actions (shadcn-mapped)."""

from __future__ import annotations

from dataclasses import dataclass

from rich.console import Group, RenderableType
from rich.text import Text

from downcroc.cli.design.components.breadcrumb_bar import BreadcrumbBar
from downcroc.cli.design.primitives.kbd import kbd
from downcroc.cli.design.primitives.text import label
from downcroc.cli.design.theme import DEFAULT, Theme


@dataclass(frozen=True)
class TopbarAction:
    id: str
    label: str
    hint: str = ""


def render_topbar(
    crumbs: list[str],
    actions: list[TopbarAction] | None = None,
    *,
    theme: Theme = DEFAULT,
    meta: str = "",
) -> RenderableType:
    items = [
        (c, "active" if i == len(crumbs) - 1 else "default")
        for i, c in enumerate(crumbs)
    ]
    parts: list[RenderableType] = [BreadcrumbBar(items, theme)]
    if meta:
        parts.append(label(f"  ·  {meta}", theme, tone="fg_faint"))
    if actions:
        action_text = Text("  ")
        for i, action in enumerate(actions):
            if i:
                action_text.append("  ", style=theme.style("bg_page"))
            action_text.append(action.label, style=theme.style("fg_muted"))
            if action.hint:
                action_text.append(" ")
                action_text.append_text(kbd(action.hint, theme))
        parts.append(action_text)
    return Group(*parts)
