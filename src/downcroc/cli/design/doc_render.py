"""Render parsed docs pages/blocks through the design system.

Bridges the existing docs parser (``cli.docs.model``) to design bricks so we
can test markdown rendering with real docs content before the full typed block
model and shell land.
"""

from __future__ import annotations

from rich.console import Group
from rich.markdown import Markdown
from rich.text import Text

from downcroc.cli.design.primitives.callout import Callout
from downcroc.cli.design.primitives.code_panel import CodePanel
from downcroc.cli.design.primitives.rule import divider
from downcroc.cli.design.primitives.table_view import TableView
from downcroc.cli.design.primitives.text import heading, prose
from downcroc.cli.design.theme import Theme
from downcroc.cli.docs import model


def render_block(block: model.Block, theme: Theme, *, width: int = 72) -> object:
    if block.kind == "code":
        return CodePanel(
            block.text,
            theme,
            language=block.language or "text",
            filename=block.language or "text",
            width=width,
        )
    if block.kind == "mermaid":
        return Callout("diagram", "mermaid diagram (terminal view)", theme, tone="note")
    if block.kind == "callout":
        return Callout(block.title, block.text, theme, tone=block.tone)
    if block.kind == "image":
        return Text(
            f"[image] {block.text}  {block.title}", style=theme.style("fg_muted")
        )
    if block.kind == "table":
        headers, rows = model.table_rows(block.text)
        if not headers:
            return Text(block.text, style=theme.style("fg_secondary"))
        return TableView(headers, rows, theme, width=width)
    return Markdown(block.text)


def render_page(page: model.Page, theme: Theme, *, width: int = 72) -> Group:
    parts: list[object] = [heading(page.title, theme, level=1)]
    if page.description:
        parts.append(prose(page.description, theme))
    parts.append(Text(""))
    parts.append(divider(theme, width=min(width, 60)))
    parts.append(Text(""))
    body = page.body
    for block in model.blocks(body):
        parts.append(render_block(block, theme, width=width))
        parts.append(Text(""))
    return Group(*parts)
