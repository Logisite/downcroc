"""Playground: the live app for reviewing the design system.

Run ``uv run python -m downcroc.cli.design.playground`` to see the bricks
in a real Textual screen. Headless exports live in gallery.py.
"""

from __future__ import annotations

from typing import ClassVar

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widget import Widget

from downcroc.cli.design.primitives.card import Card
from downcroc.cli.design.primitives.code_panel import sample_panel
from downcroc.cli.design.primitives.keybar import keybar
from downcroc.cli.design.primitives.text import chip, heading, label, prose
from downcroc.cli.design.theme import DEFAULT


class Brick(Widget):
    """Minimal wrapper: renders a Rich renderable inside the app."""

    def __init__(self, renderable: object) -> None:
        super().__init__()
        self._renderable = renderable

    def render(self) -> object:
        return self._renderable


class PlaygroundApp(App):
    """One screen, every brick, on the page background."""

    CSS = """
    Screen { background: #000000; }
    #gallery { padding: 1 2; }
    """

    BINDINGS: ClassVar = [("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        with Vertical(id="gallery"):
            yield Brick(heading("playground", DEFAULT))
            yield Brick(Text(" "))
            yield Brick(label("bricks", DEFAULT))
            yield Brick(
                prose("Body text from the fg scale, never pure white.", DEFAULT)
            )
            yield Brick(chip("inline-code", DEFAULT))
            yield Brick(Text(" "))
            yield Brick(
                Card(
                    "watcher",
                    "The inbound watcher hands work to the ingester.",
                    DEFAULT,
                    width=44,
                )
            )
            yield Brick(Text(" "))
            yield Brick(
                Card(
                    "hairline variant",
                    "Same card, barely-visible alpha border.",
                    DEFAULT,
                    width=44,
                    border="hairline",
                )
            )
            yield Brick(Text(" "))
            yield Brick(sample_panel(DEFAULT))
            yield Brick(Text(" "))
            yield Brick(
                keybar([("enter", "open"), ("?", "keys"), ("q", "quit")], DEFAULT)
            )


def run() -> None:
    PlaygroundApp().run()


if __name__ == "__main__":
    run()
