from __future__ import annotations

from rich import box
from rich.console import Group
from rich.padding import Padding
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text


def hero(title: str, description: str, width: int) -> Group:
    line = Text()
    line.append(title, style="bold #f8fafc")
    body = Text(description, style="#94a3b8")
    actions = Text()
    for label in ("Install", "Connect a mailbox", "Read the concepts"):
        actions.append(f"  {label}  ", style="bold #0b1020 on #67e8f9")
        actions.append("  ")
    return Group(
        Panel(
            Group(Text(""), line, Text(""), body, Text(""), actions, Text("")),
            box=box.ROUNDED,
            border_style="#334155",
            padding=(1, 2),
            width=width,
        )
    )


def card(title: str, body: str, *, width: int | None = None) -> Panel:
    content = Group(
        Text(title, style="bold #f8fafc"),
        Text(body, style="#94a3b8"),
    )
    return Panel(
        content,
        box=box.ROUNDED,
        border_style="#334155",
        padding=(0, 1),
        width=width,
    )


def card_row(cards: list[tuple[str, str]], width: int) -> object:
    if width < 70:
        return Group(*[card(title, body) for title, body in cards])
    table = Table.grid(expand=True, padding=(0, 1))
    for _ in cards:
        table.add_column(ratio=1)
    table.add_row(*[card(title, body) for title, body in cards])
    return table


def code(title: str, source: str, language: str) -> Panel:
    return Panel(
        Syntax(
            source,
            language or "text",
            theme="ansi_dark",
            word_wrap=True,
            background_color="default",
        ),
        title=f" {title} ",
        title_align="left",
        border_style="#334155",
        box=box.ROUNDED,
        padding=(0, 1),
    )


def callout(title: str, body: str, tone: str = "#67e8f9") -> Group:
    label = Text(f"▌ {title}", style=f"bold {tone}")
    return Group(label, Padding(Text(body, style="#cbd5e1"), (0, 0, 0, 2)))


def section(title: str) -> Text:
    return Text(title, style="bold #f8fafc")


def keybar(items: list[tuple[str, str]]) -> Text:
    line = Text()
    for key, label in items:
        line.append(f" {key} ", style="bold #0b1020 on #94a3b8")
        line.append(f" {label}  ", style="#94a3b8")
    return line
