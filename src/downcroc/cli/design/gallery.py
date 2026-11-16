"""Headless gallery: renders every brick for screenshots and diffs.

This is the design-review loop without a terminal: ``export_gallery_svg``
writes a terminal-window SVG of the bricks (turn it into a PNG with
cairosvg), ``export_gallery_text`` gives a quick ANSI text diff.
"""

from __future__ import annotations

from rich.console import Console
from rich.terminal_theme import TerminalTheme
from rich.text import Text

from downcroc.cli.design.primitives.card import Card
from downcroc.cli.design.primitives.code_panel import sample_panel, sample_shell
from downcroc.cli.design.primitives.keybar import keybar
from downcroc.cli.design.primitives.text import chip, heading, label, prose
from downcroc.cli.design.theme import DEFAULT

FG = (201, 209, 217)

EXPORT_THEME = TerminalTheme(
    background=(0, 0, 0),
    foreground=FG,
    normal=[
        (61, 68, 81),  # black
        (248, 81, 73),  # red
        (63, 185, 80),  # green
        (210, 153, 34),  # yellow
        (88, 166, 255),  # blue
        (188, 140, 255),  # magenta
        (107, 217, 213),  # cyan
        (201, 209, 217),  # white
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


def gallery_console(width: int = 78) -> Console:
    """Render every brick to a recording console, headless."""
    console = Console(
        record=True,
        width=width,
        force_terminal=True,
        color_system="truecolor",
    )
    console.print(heading("downcroc design system", DEFAULT))
    console.print()
    console.print(label("text bricks", DEFAULT))
    console.print(prose("Body text from the fg scale, never pure white.", DEFAULT))
    console.print(chip("inline-code", DEFAULT))
    console.print()
    console.print(label("card", DEFAULT))
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
    console.print()
    console.print(label("code panels", DEFAULT))
    console.print(sample_panel(DEFAULT))
    console.print()
    console.print(sample_shell(DEFAULT))
    console.print()
    console.print(label("keybar", DEFAULT))
    console.print(keybar([("enter", "open"), ("?", "keys"), ("q", "quit")], DEFAULT))
    console.print(Text(""))
    return console


def export_gallery_svg(path: str) -> str:
    """Write the brick gallery as an SVG screenshot and return its path."""
    console = gallery_console()
    svg = console.export_svg(
        title="downcroc design system",
        theme=EXPORT_THEME,
        font_aspect_ratio=0.6,
    )
    # cairosvg ignores textLength, so the declared font must have the exact
    # advance Rich assumes (0.6 em) and cover box-drawing corners: JetBrains
    # Mono does both, Fira Code lacks the arcs.
    svg = svg.replace("Fira Code", "JetBrains Mono")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(svg)
    return path


def export_gallery_text() -> str:
    """Render the gallery as plain text, for quick diffs."""
    console = gallery_console()
    return console.export_text(styles=True)
