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
from downcroc.cli.design.primitives.spacer import spacer
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
from downcroc.cli.design.samples.data_samples import (
    KV_COMPACT,
    KV_ITEMS,
    LIST_ITEMS,
    ORDERED_ITEMS,
    TABLE_ALIGN,
    TABLE_HEADERS,
    TABLE_ROWS,
    TASK_ITEMS,
)
from downcroc.cli.design.samples.feedback_samples import (
    CALLOUTS,
    NAV_ITEMS,
    TOASTS,
    TOC_ITEMS,
)
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
    parts: list[object] = [
        SectionHeader("Tokens", theme, meta="surfaces, text, accents")
    ]
    for name, token in [
        ("page", "bg_page"),
        ("panel", "bg_panel"),
        ("raised", "bg_raised"),
        ("inset", "bg_inset"),
    ]:
        parts.append(_swatch(name, token, theme))
    parts.append(spacer(1, theme=theme))
    for name, token in [
        ("primary", "fg_primary"),
        ("secondary", "fg_secondary"),
        ("muted", "fg_muted"),
        ("faint", "fg_faint"),
    ]:
        parts.append(_swatch(name, token, theme))
    parts.append(spacer(1, theme=theme))
    for name, token in [
        ("accent", "accent"),
        ("success", "success"),
        ("warning", "warning"),
        ("danger", "danger"),
        ("info", "info"),
    ]:
        parts.append(_swatch(name, token, theme))
    parts.append(spacer(1, theme=theme))
    return Group(*parts)


def _text_section(theme: Theme) -> Group:
    parts: list[object] = [
        SectionHeader("Text primitives", theme, meta="hierarchy, inline, prose")
    ]
    parts.append(label("breadcrumb / headings / labels", theme))
    parts.append(breadcrumb(BREADCRUMB_SAMPLE, theme))
    parts.append(spacer(1, theme=theme))
    for level, text in HEADING_SAMPLES:
        parts.append(heading(text, theme, level=level))
    parts.append(spacer(1, theme=theme))
    for text, tone in LABEL_SAMPLES:
        parts.append(label(text, theme, tone=tone))
    parts.append(spacer(1, theme=theme))
    parts.append(label("prose and inline", theme))
    parts.append(prose(PROSE_SAMPLE, theme, width=62))
    parts.append(spacer(1, theme=theme))
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
    parts.append(spacer(1, theme=theme))
    badges = Text()
    badges.append_text(badge("queued", theme, tone="info"))
    badges.append("  ")
    badges.append_text(badge("sent", theme, tone="success"))
    badges.append("  ")
    badges.append_text(badge("warning", theme, tone="warning"))
    badges.append("  ")
    badges.append_text(badge("error", theme, tone="danger", variant="solid"))
    badges2 = Text()
    badges2.append_text(badge("beta", theme, tone="accent", variant="outline"))
    badges2.append("  ")
    badges2.append_text(badge("ok", theme, tone="success", variant="solid"))
    badges2.append("  ")
    badges2.append_text(badge("muted", theme, tone="fg_muted", variant="subtle"))
    parts.append(label("badges", theme))
    parts.append(badges)
    parts.append(badges2)
    parts.append(spacer(1, theme=theme))
    parts.append(label("blockquote", theme))
    parts.append(
        Blockquote(
            "Queued means written down and waiting. Nothing has gone to the mail server yet.",
            theme,
            cite="docs",
        )
    )
    return Group(*parts)


def _surfaces_section(theme: Theme) -> Group:
    parts: list[object] = [
        SectionHeader("Surfaces / structure", theme, meta="card, panel, figure, rule")
    ]
    parts.append(label("cards", theme))
    parts.append(
        Card(
            "watcher",
            "The inbound watcher hands work to the ingester.",
            theme,
            width=44,
        )
    )
    parts.append(
        Card(
            "hairline variant",
            "Same card, barely-visible alpha border.",
            theme,
            width=44,
            border="hairline",
        )
    )
    parts.append(spacer(1, theme=theme))
    parts.append(label("panel + figure", theme))
    parts.append(Panel("A generic panel surface for grouped content.", theme, width=48))
    parts.append(
        Figure(
            Panel("Figure content block", theme, width=36, fill="bg_inset"),
            theme,
            caption="Figure: compact inset panel sample",
        )
    )
    parts.append(divider(theme, width=44, label="section divider"))
    parts.append(spacer(1, theme=theme))
    return Group(*parts)


def _data_section(theme: Theme) -> Group:
    parts: list[object] = [
        SectionHeader(
            "Data & collections", theme, meta="table, key-value, lists, empty"
        )
    ]
    parts.append(label("tables", theme))
    parts.append(TableView(TABLE_HEADERS, TABLE_ROWS, theme, align=TABLE_ALIGN))
    parts.append(spacer(1, theme=theme))
    parts.append(Text("compact, zebra off", style=theme.style("fg_faint")))
    parts.append(
        TableView(
            ["Field", "Value"],
            [["mode", "compact"], ["zebra", "off"]],
            theme,
            compact=True,
            zebra=False,
        )
    )
    parts.append(spacer(1, theme=theme))
    parts.append(Text("empty (header shown)", style=theme.style("fg_faint")))
    parts.append(
        TableView(
            ["Field", "Value"],
            [],
            theme,
            compact=True,
            empty_text="No data yet",
            show_header_on_empty=True,
        )
    )
    parts.append(spacer(1, theme=theme))
    parts.append(label("key-value", theme))
    parts.append(KeyValue(KV_ITEMS, theme))
    parts.append(KeyValue(KV_COMPACT, theme, compact=True, divider=True))
    parts.append(spacer(1, theme=theme))
    parts.append(label("lists", theme))
    parts.append(ListBlock(LIST_ITEMS, theme))
    parts.append(spacer(1, theme=theme))
    parts.append(ListBlock(ORDERED_ITEMS, theme, ordered=True))
    parts.append(spacer(1, theme=theme))
    parts.append(ListBlock(TASK_ITEMS, theme, task=True))
    parts.append(spacer(1, theme=theme))
    parts.append(label("empty states", theme))
    parts.append(
        EmptyState(
            "No batches yet",
            theme,
            body="Create one to get started.",
            hint="Press b to create a batch",
        )
    )
    parts.append(EmptyState("Nothing selected", theme, compact=True))
    return Group(*parts)


def _code_section(theme: Theme) -> Group:
    parts: list[object] = [
        SectionHeader("Code panels", theme, meta="chrome, states, highlight")
    ]
    parts.append(Text("default (highlighted line)", style=theme.style("fg_faint")))
    parts.append(
        CodePanel(
            sample_panel(theme).source,
            theme,
            language="python",
            filename="runtime/service/lifecycle.py",
            width=72,
            highlight_lines={3},
        )
    )
    parts.append(spacer(1, theme=theme))
    parts.append(Text("copied state", style=theme.style("fg_faint")))
    parts.append(
        CodePanel(
            sample_shell(theme).source,
            theme,
            language="bash",
            filename="deploy.sh",
            width=72,
            copied=True,
        )
    )
    parts.append(spacer(1, theme=theme))
    parts.append(Text("disabled copy state", style=theme.style("fg_faint")))
    parts.append(
        CodePanel(
            sample_shell(theme).source,
            theme,
            language="bash",
            filename="deploy.sh",
            width=72,
            button_state="disabled",
        )
    )
    parts.append(spacer(1, theme=theme))
    return Group(*parts)


def _feedback_nav_section(theme: Theme) -> Group:
    parts: list[object] = [
        SectionHeader(
            "Buttons, feedback & navigation", theme, meta="states and variants"
        )
    ]
    parts.append(label("button states (primary)", theme))
    for state in ["default", "hover", "focus", "pressed", "disabled"]:
        parts.append(
            Columns(
                [
                    Text(f"primary/{state:<8}", style=theme.style("fg_faint")),
                    Button("Send", theme, variant="primary", state=state),
                ],
                expand=False,
                padding=(0, 1),
            )
        )
    parts.append(spacer(1, theme=theme))
    parts.append(label("button variants", theme))
    parts.append(
        Columns(
            [
                Button("Secondary", theme, variant="secondary"),
                Button("Ghost", theme, variant="ghost"),
                Button("Danger", theme, variant="danger"),
                Button("Search", theme, variant="secondary", icon="search"),
            ],
            expand=False,
            padding=(0, 1),
        )
    )
    parts.append(spacer(1, theme=theme))
    parts.append(label("callout tones", theme))
    for title, tone, icon_name, body in CALLOUTS:
        parts.append(Callout(title, body, theme, tone=tone, icon=icon_name, width=58))
    parts.append(label("toasts", theme))
    for message, tone in TOASTS:
        parts.append(Toast(message, theme, tone=tone))
    parts.append(label("icons", theme))
    icons_line = Text()
    for name in ["account", "inbox", "sent", "search", "settings"]:
        icons_line.append_text(icon(name, theme, tone="fg_muted"))
        icons_line.append("  ", style=theme.style("bg_page"))
    icons_line.append_text(status_dot(theme, tone="success"))
    icons_line.append(" online  ", style=theme.style("fg_muted"))
    icons_line.append_text(status_dot(theme, tone="warning"))
    icons_line.append(" syncing", style=theme.style("fg_muted"))
    parts.append(icons_line)
    parts.append(spacer(1, theme=theme))
    parts.append(label("nav items / states", theme))
    for nav_label, nav_icon, active, indent, nav_badge in NAV_ITEMS:
        parts.append(
            NavItem(
                nav_label,
                theme,
                icon=nav_icon,
                active=active,
                indent=indent,
                badge_text=nav_badge,
                width=56,
            )
        )
    parts.append(NavItem("Drafts", theme, icon="folder", state="hover", width=56))
    parts.append(NavItem("Settings", theme, icon="settings", state="focus", width=56))
    parts.append(NavItem("Disabled", theme, icon="folder", state="disabled", width=56))
    parts.append(spacer(1, theme=theme))
    parts.append(label("toc items / states", theme))
    for toc_label, level, active in TOC_ITEMS:
        parts.append(TocItem(toc_label, theme, level=level, active=active))
    parts.append(TocItem("Advanced", theme, level=1, state="hover"))
    parts.append(TocItem("Keyboard", theme, level=2, state="focus"))
    parts.append(spacer(1, theme=theme))
    parts.append(label("tags", theme))
    parts.append(TagList(["mailbox", "sync", "beta"], theme))
    parts.append(spacer(1, theme=theme))
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
    console.print(
        Text(
            "primitives-first gallery — in-package samples, screenshot/critique loop",
            style=DEFAULT.style("fg_muted"),
        )
    )
    console.print(spacer(1, theme=DEFAULT))
    console.print(_token_section(DEFAULT))
    console.print(_text_section(DEFAULT))
    console.print(_surfaces_section(DEFAULT))
    console.print(_data_section(DEFAULT))
    console.print(_code_section(DEFAULT))
    console.print(_feedback_nav_section(DEFAULT))
    console.print(label("keybar", DEFAULT))
    console.print(keybar([("enter", "open"), ("?", "keys"), ("q", "quit")], DEFAULT))
    console.print(spacer(1, theme=DEFAULT))
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
