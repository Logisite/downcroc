"""Headless gallery: renders every brick for screenshots and diffs.

This is the design-review loop without a terminal: ``export_gallery_svg``
writes a terminal-window SVG of the bricks (turn it into a PNG with
cairosvg), ``export_gallery_text`` gives a quick ANSI text diff.
"""

from __future__ import annotations

import io

from rich.console import Console, Group
from rich.terminal_theme import TerminalTheme
from rich.text import Text

from downcroc.cli.design.primitives.badge import badge
from downcroc.cli.design.primitives.blockquote import Blockquote
from downcroc.cli.design.primitives.callout import Callout
from downcroc.cli.design.primitives.card import Card
from downcroc.cli.design.primitives.code_panel import sample_panel, sample_shell
from downcroc.cli.design.primitives.keybar import keybar
from downcroc.cli.design.primitives.rule import divider
from downcroc.cli.design.primitives.table_view import TableView
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
    console.print(sample_panel(DEFAULT))
    console.print(Text(""))
    console.print(sample_shell(DEFAULT))
    console.print(Text(""))
    console.print(label("rule / callout / table", DEFAULT))
    console.print(divider(DEFAULT, width=44, label="section"))
    console.print(
        Callout("Note", "This is a sample callout brick.", DEFAULT, tone="note")
    )
    console.print(
        TableView(
            ["Field", "Value"],
            [["account", "alice@example.com"], ["status", "queued"]],
            DEFAULT,
        )
    )
    console.print(Text(""))
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
