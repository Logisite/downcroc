from __future__ import annotations

from rich import box
from rich.console import Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from downcroc.cli.docs import blocks, model

TONES = {
    "note": "cyan",
    "tip": "green",
    "warning": "yellow",
    "danger": "red",
    "example": "cyan",
    "quote": "dim",
}


def page_renderable(page: model.Page, width: int, *, plain: bool = False) -> Group:
    if page.rel == "index.md":
        return home_renderable(page, width, plain=plain)
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


def home_renderable(page: model.Page, width: int, *, plain: bool = False) -> Group:
    del plain
    cards = [
        ("01  Install", "One command. Linux and Windows."),
        ("02  Connect", "OAuth or app password. Verify with doctor."),
        ("03  Send", "Preview, approve, and follow up."),
    ]
    local = [
        ("Vault", "encrypted"),
        ("SQLite", "local"),
        ("Content", "local"),
        ("JSONL logs", "local"),
    ]
    return Group(
        blocks.hero(page.title, page.description, width),
        Text(""),
        blocks.code(
            "install",
            "curl -fsSL https://raw.githubusercontent.com/Logisite/downcroc/master/scripts/install.sh | sh",
            "bash",
        ),
        Text(""),
        blocks.card_row(cards, width),
        Text(""),
        blocks.section("What stays local"),
        blocks.card_row(local, width),
    )


def _card_row(cards: list[tuple[str, str]], width: int, plain: bool) -> object:
    if width < 70:
        return Group(
            *[
                Panel(
                    Text(f"{title}\n{body}", style="dim" if plain else ""),
                    box=box.ROUNDED,
                    border_style="dim",
                    padding=(0, 1),
                )
                for title, body in cards
            ]
        )
    table = Table.grid(expand=True, padding=(0, 1))
    for _ in cards:
        table.add_column(ratio=1)
    table.add_row(
        *[
            Panel(
                Text(f"{title}\n{body}", style="dim" if plain else ""),
                box=box.ROUNDED,
                border_style="dim",
                padding=(0, 1),
            )
            for title, body in cards
        ]
    )
    return table


def _block(block: model.Block, width: int, plain: bool) -> object:
    if block.kind == "code":
        return blocks.code(block.language or "text", block.text, block.language)
    if block.kind == "mermaid":
        return Panel(
            Text("diagram omitted in the terminal\ndowncroc docs --open shows it"),
            title=" diagram ",
            border_style="dim",
            box=box.ROUNDED,
        )
    if block.kind == "callout":
        return blocks.callout(block.title, block.text, TONES.get(block.tone, "#67e8f9"))
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
