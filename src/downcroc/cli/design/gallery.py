"""Headless gallery: renders every brick for screenshots and diffs.

This is the design-review loop without a terminal: ``export_gallery_svg``
writes a terminal-window SVG of the bricks (turn it into a PNG with
cairosvg), ``export_gallery_text`` gives a quick ANSI text diff.
"""

from __future__ import annotations

import io

from rich.columns import Columns
from rich.console import Console, Group
from rich.terminal_theme import TerminalTheme
from rich.text import Text

from downcroc.cli.design.primitives.badge import badge
from downcroc.cli.design.primitives.blockquote import Blockquote
from downcroc.cli.design.primitives.button import Button
from downcroc.cli.design.primitives.callout import Callout
from downcroc.cli.design.primitives.card import Card
from downcroc.cli.design.primitives.code_panel import (
    CodePanel,
    sample_panel,
    sample_shell,
)
from downcroc.cli.design.primitives.empty_state import EmptyState
from downcroc.cli.design.primitives.figure import Figure
from downcroc.cli.design.primitives.icon import icon, status_dot
from downcroc.cli.design.primitives.key_value import KeyValue
from downcroc.cli.design.primitives.keybar import keybar
from downcroc.cli.design.primitives.list_block import ListBlock
from downcroc.cli.design.primitives.nav import NavItem, TocItem
from downcroc.cli.design.primitives.panel import Panel
from downcroc.cli.design.primitives.rule import divider
from downcroc.cli.design.primitives.section_header import SectionHeader
from downcroc.cli.design.primitives.table_view import TableView
from downcroc.cli.design.primitives.tag_list import TagList
from downcroc.cli.design.primitives.text import (
    breadcrumb,
    heading,
    inline_code,
    label,
    link_text,
    muted,
    prose,
    strong,
    truncate,
)
from downcroc.cli.design.primitives.toast import Toast
from downcroc.cli.design.samples.text_samples import (
    BREADCRUMB_SAMPLE,
    HEADING_SAMPLES,
    LABEL_SAMPLES,
    PROSE_SAMPLE,
)
from downcroc.cli.design.theme import DEFAULT, Theme

FG = (201, 209, 217)

EXPORT_THEME = TerminalTheme(
    background=(0, 0, 0),
    foreground=FG,
    normal=[
        (61, 68, 81),
        (248, 81, 73),
        (63, 185, 80),
        (210, 153, 34),
        (88, 166, 255),
        (188, 140, 255),
        (107, 217, 213),
        (201, 209, 217),
    ],
    bright=[
        (98, 108, 122),
        (248, 81, 73),
        (63, 185, 80),
        (210, 153, 34),
        (88, 166, 255),
        (188, 140, 255),
        (107, 217, 213),
        (255, 255, 255),
    ],
)


def _swatch(name: str, token: str, theme: Theme) -> Text:
    color = getattr(theme, token)
    line = Text()
    line.append("▕", style=theme.style("border_strong"))
    line.append("████", style=f"{color} on {color}")
    line.append("▏", style=theme.style("border_strong"))
    line.append(f" {name:<14}", style=theme.style("fg_secondary"))
    line.append(color, style=theme.style("fg_faint"))
    return line


def _token_section(theme: Theme) -> Group:
    parts: list[object] = [label("tokens", theme), Text("")]
    for name, token in [
        ("page", "bg_page"),
        ("panel", "bg_panel"),
        ("raised", "bg_raised"),
        ("inset", "bg_inset"),
    ]:
        parts.append(_swatch(name, token, theme))
    parts.append(Text(""))
    for name, token in [
        ("primary", "fg_primary"),
        ("secondary", "fg_secondary"),
        ("muted", "fg_muted"),
        ("faint", "fg_faint"),
    ]:
        parts.append(_swatch(name, token, theme))
    parts.append(Text(""))
    for name, token in [
        ("accent", "accent"),
        ("success", "success"),
        ("warning", "warning"),
        ("danger", "danger"),
        ("info", "info"),
    ]:
        parts.append(_swatch(name, token, theme))
    return Group(*parts)


def _text_section(theme: Theme) -> Group:
    parts: list[object] = [label("text primitives", theme), Text("")]
    parts.append(breadcrumb(BREADCRUMB_SAMPLE, theme))
    parts.append(Text(""))
    for level, text in HEADING_SAMPLES:
        parts.append(heading(text, theme, level=level))
    parts.append(Text(""))
    for text, tone in LABEL_SAMPLES:
        parts.append(label(text, theme, tone=tone))
    parts.append(Text(""))
    parts.append(prose(PROSE_SAMPLE, theme, width=62))
    parts.append(Text(""))
    inline = Text()
    inline.append("Body with ", style=theme.style("fg_secondary"))
    inline.append_text(inline_code("inline_code()", theme))
    inline.append(", ", style=theme.style("fg_secondary"))
    inline.append_text(link_text("a link", theme, href="https://example.com"))
    inline.append(", ", style=theme.style("fg_secondary"))
    inline.append_text(strong("strong", theme))
    inline.append(", and ", style=theme.style("fg_secondary"))
    inline.append_text(muted("muted", theme))
    inline.append(".", style=theme.style("fg_secondary"))
    parts.append(inline)
    parts.append(
        Text(
            f"truncate: {truncate('a very long identifier name', 18)}",
            style=theme.style("fg_muted"),
        )
    )
    parts.append(Text(""))
    badges = Text()
    badges.append_text(badge("queued", theme, tone="info"))
    badges.append("  ")
    badges.append_text(badge("sent", theme, tone="success"))
    badges.append("  ")
    badges.append_text(badge("warning", theme, tone="warning"))
    badges.append("  ")
    badges.append_text(badge("error", theme, tone="danger", variant="solid"))
    parts.append(badges)
    parts.append(Text(""))
    parts.append(
        Blockquote(
            "Queued means written down and waiting. Nothing has gone to the mail server yet.",
            theme,
            cite="docs",
        )
    )
    return Group(*parts)


def gallery_console(width: int = 78) -> Console:
    """Render every brick to a recording console, headless."""
    console = Console(
        record=True,
        width=width,
        force_terminal=True,
        color_system="truecolor",
        file=io.StringIO(),
    )
    console.print(heading("downcroc design system", DEFAULT))
    console.print(Text(""))
    console.print(_token_section(DEFAULT))
    console.print(Text(""))
    console.print(_text_section(DEFAULT))
    console.print(Text(""))
    console.print(label("surfaces", DEFAULT))
    console.print(
        Card(
            "watcher",
            "The inbound watcher hands work to the ingester.",
            DEFAULT,
            width=44,
        )
    )
    console.print(
        Card(
            "hairline variant",
            "Same card, barely-visible alpha border.",
            DEFAULT,
            width=44,
            border="hairline",
        )
    )
    console.print(Text(""))
    console.print(label("code panels", DEFAULT))
    console.print(
        CodePanel(
            sample_panel(DEFAULT).source,
            DEFAULT,
            language="python",
            filename="runtime/service/lifecycle.py",
            width=72,
            highlight_lines={3},
        )
    )
    console.print(Text(""))
    console.print(
        CodePanel(
            sample_shell(DEFAULT).source,
            DEFAULT,
            language="bash",
            filename="deploy.sh",
            width=72,
            button_state="disabled",
        )
    )
    console.print(Text(""))
    console.print(label("rule / callout / table", DEFAULT))
    console.print(divider(DEFAULT, width=44, label="section"))
    console.print(
        Callout(
            "Note",
            "This is a sample callout brick with wrapped body text to show flow inside the tinted surface.",
            DEFAULT,
            tone="note",
            icon="info",
            width=58,
        )
    )
    console.print(
        TableView(
            ["Field", "Value", "Count"],
            [["account", "alice@example.com", "12"], ["status", "queued", "3"]],
            DEFAULT,
            align=["left", "left", "right"],
        )
    )
    console.print(
        TableView(
            ["Field", "Value"],
            [["mode", "compact"], ["zebra", "off"]],
            DEFAULT,
            compact=True,
            zebra=False,
        )
    )
    console.print(
        TableView(
            ["Field", "Value"],
            [],
            DEFAULT,
            compact=True,
            empty_text="No data yet",
            show_header_on_empty=True,
        )
    )
    console.print(Text(""))
    console.print(label("panel / key-value / lists / empty", DEFAULT))
    console.print(
        Panel("A generic panel surface for grouped content.", DEFAULT, width=48)
    )
    console.print(Text(""))
    console.print(
        KeyValue(
            [
                ("account", "alice@example.com"),
                ("mailbox", "inbox"),
                ("state", "connected"),
            ],
            DEFAULT,
        )
    )
    console.print(
        KeyValue(
            [("mode", "compact"), ("sync", "idle")],
            DEFAULT,
            compact=True,
            divider=True,
        )
    )
    console.print(Text(""))
    console.print(
        ListBlock(
            [
                "Queued and waiting",
                "Accepted by server and visible in sent folder history for later review",
                "Visible in sent folder",
            ],
            DEFAULT,
        )
    )
    console.print(
        ListBlock(["Create job", "Review batch", "Send"], DEFAULT, ordered=True)
    )
    console.print(
        ListBlock(
            [
                ("Connect mailbox", 0, True),
                ("Send first email", 0, False),
                ("Check logs", 0, False),
            ],
            DEFAULT,
            task=True,
        )
    )
    console.print(
        EmptyState(
            "No batches yet",
            DEFAULT,
            body="Create one to get started.",
            hint="Press b to create a batch",
        )
    )
    console.print(EmptyState("Nothing selected", DEFAULT, compact=True))
    console.print(Text(""))
    console.print(label("buttons / icons / nav / toc / tags / feedback", DEFAULT))
    for state in ["default", "hover", "focus", "pressed", "disabled"]:
        console.print(
            Columns(
                [
                    Text(f"primary/{state:<8}", style=DEFAULT.style("fg_faint")),
                    Button("Send", DEFAULT, variant="primary", state=state),
                ],
                expand=False,
                padding=(0, 1),
            )
        )
    console.print(
        Columns(
            [
                Button(variant.title(), DEFAULT, variant=variant)
                for variant in ["secondary", "ghost", "danger"]
            ]
            + [Button("Search", DEFAULT, variant="secondary", icon="search")],
            expand=False,
            padding=(0, 1),
        )
    )
    console.print(Text(""))
    console.print(SectionHeader("Mailbox status", DEFAULT, meta="3 accounts"))
    console.print(
        Figure(
            Panel("Figure content block", DEFAULT, width=36, fill="bg_inset"),
            DEFAULT,
            caption="Figure: compact inset panel sample",
        )
    )
    icons_line = Text()
    for name in ["account", "inbox", "sent", "search", "settings"]:
        icons_line.append_text(icon(name, DEFAULT, tone="fg_muted"))
        icons_line.append("  ", style=DEFAULT.style("bg_page"))
    icons_line.append_text(status_dot(DEFAULT, tone="success"))
    icons_line.append(" online  ", style=DEFAULT.style("fg_muted"))
    icons_line.append_text(status_dot(DEFAULT, tone="warning"))
    icons_line.append(" syncing", style=DEFAULT.style("fg_muted"))
    console.print(icons_line)
    console.print(Text(""))
    console.print(NavItem("Inbox", DEFAULT, icon="inbox", active=True, badge_text="12"))
    console.print(NavItem("Sent", DEFAULT, icon="sent"))
    console.print(NavItem("Archive", DEFAULT, icon="folder", indent=1))
    console.print(Text(""))
    console.print(TocItem("Overview", DEFAULT, level=1, active=True))
    console.print(TocItem("Setup", DEFAULT, level=1))
    console.print(TocItem("Troubleshooting", DEFAULT, level=2))
    console.print(Text(""))
    console.print(TagList(["mailbox", "sync", "beta"], DEFAULT))
    console.print(Text(""))
    console.print(Toast("Connected to mailbox", DEFAULT, tone="success"))
    console.print(Toast("Retry scheduled", DEFAULT, tone="warning"))
    console.print(Toast("Delivery failed", DEFAULT, tone="danger"))
    console.print(Toast("Sync info", DEFAULT, tone="info"))
    console.print(label("keybar", DEFAULT))
    console.print(keybar([("enter", "open"), ("?", "keys"), ("q", "quit")], DEFAULT))
    console.print(Text(""))
    return console


def export_gallery_svg(path: str) -> str:
    console = gallery_console()
    svg = console.export_svg(
        title="downcroc design system",
        theme=EXPORT_THEME,
        font_aspect_ratio=0.6,
    )
    svg = svg.replace("Fira Code", "JetBrains Mono")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(svg)
    return path


def export_gallery_text() -> str:
    console = gallery_console()
    return console.export_text(styles=True)
