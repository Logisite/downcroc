"""Dialog/Sheet primitives (shadcn Dialog/Sheet mapping, Textual-friendly models)."""

from __future__ import annotations

from dataclasses import dataclass

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.text import Text

from downcroc.cli.design.theme import DEFAULT, Theme


@dataclass(frozen=True)
class DialogSpec:
    title: str
    description: str = ""
    content: RenderableType | None = None
    footer: RenderableType | None = None


def render_dialog(
    spec: DialogSpec, theme: Theme = DEFAULT, *, width: int = 72
) -> Panel:
    parts: list[RenderableType] = [
        Text(spec.title, style=theme.style("fg_primary", bold=True))
    ]
    if spec.description:
        parts.append(Text(spec.description, style=theme.style("fg_muted")))
        parts.append(Text(""))
    if spec.content is not None:
        parts.append(spec.content)
    if spec.footer is not None:
        parts.append(Text(""))
        parts.append(spec.footer)
    return Panel(
        Group(*parts),
        border_style=theme.style("border_focus"),
        width=width,
        padding=(1, 2),
    )


@dataclass(frozen=True)
class SheetSpec(DialogSpec):
    side: str = "right"
