from __future__ import annotations

from rich import box
from rich.console import Group
from rich.markdown import Markdown
from rich.padding import Padding
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from downcroc.cli.docs import model

TONES = {
    "note": "cyan",
    "tip": "green",
    "warning": "yellow",
    "danger": "red",
    "example": "cyan",
    "quote": "dim",
}


def page_renderable(page: model.Page, width: int, *, plain: bool = False) -> Group:
    parts: list[object] = []
    parts.append(Text(page.title, style="" if plain else "bold"))
    parts.append(Text("─" * min(width, max(8, len(page.title) + 4)), style="dim"))
    if page.description:
        parts.append(Text(page.description, style="dim"))
        parts.append(Text(""))
    if page.toc and page.headings:
        parts.append(Text("On this page", style="bold"))
        parts.extend(Text(f"  {item}", style="dim") for item in page.headings)
        parts.append(Text(""))
    body = _without_first_h1(page.body)
    for block in model.blocks(body):
        parts.append(_block(block, width, plain))
    return Group(*parts)


def _block(block: model.Block, width: int, plain: bool) -> object:
    if block.kind == "code":
        syntax = Syntax(
            block.text,
            block.language or "text",
            theme="ansi_dark",
            word_wrap=True,
            background_color="default",
        )
        return Panel(
            syntax,
            title=f" {block.language or 'text'} ",
            title_align="left",
            border_style="dim",
            box=box.ROUNDED,
            padding=(0, 1),
        )
    if block.kind == "mermaid":
        return Panel(
            Text("diagram omitted in the terminal\ndowncroc docs --open shows it"),
            title=" diagram ",
            border_style="dim",
            box=box.ROUNDED,
        )
    if block.kind == "callout":
        tone = TONES.get(block.tone, "cyan")
        label = Text(f"▌ {block.title}", style=tone if not plain else "")
        return Group(label, Padding(Markdown(block.text), (0, 0, 0, 2)))
    if block.kind == "image":
        return Text(f"[image] {block.text}  {block.title}", style="dim")
    if block.kind == "table":
        return _table(block.text, width)
    return Markdown(block.text)


def _table(text: str, width: int) -> object:
    header, rows = model.table_rows(text)
    if not header:
        return Text(text)
    if width < 60:
        lines = []
        for row in rows:
            for key, value in zip(header, row):
                lines.append(Text(f"{key}: {value}"))
            lines.append(Text(""))
        return Group(*lines)
    table = Table(box=box.SIMPLE_HEAD, show_edge=False, pad_edge=False)
    for key in header:
        table.add_column(key)
    for row in rows:
        table.add_row(*row)
    return table


def _without_first_h1(body: str) -> str:
    lines = body.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("# "):
            lines[index] = ""
            break
    return "\n".join(lines)
