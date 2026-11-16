"""Playground: the live app for reviewing the design system.

Run ``uv run python -m downcroc.cli.design.playground`` to see the bricks
in a real Textual screen. Headless exports live in gallery.py.
"""

from __future__ import annotations

from typing import ClassVar

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Blur, Enter, Focus, Leave, MouseDown, MouseUp
from textual.widget import Widget

from downcroc.cli.design.primitives.button import Button
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


class InteractiveButton(Widget):
    """Textual-integrated demo: maps Textual focus/hover/press to Button states."""

    can_focus = True

    def __init__(self, text: str, *, variant: str = "secondary") -> None:
        super().__init__()
        self._text = text
        self._variant = variant
        self._state = "default"

    def _set_state(self, state: str) -> None:
        if self._state != state:
            self._state = state
            self.refresh()

    def on_enter(self, _: Enter) -> None:
        if not self.has_focus:
            self._set_state("hover")

    def on_leave(self, _: Leave) -> None:
        if not self.has_focus:
            self._set_state("default")

    def on_focus(self, _: Focus) -> None:
        self._set_state("focus")

    def on_blur(self, _: Blur) -> None:
        self._set_state("default")

    def on_mouse_down(self, _: MouseDown) -> None:
        self._set_state("pressed")

    def on_mouse_up(self, _: MouseUp) -> None:
        self._set_state("focus" if self.has_focus else "hover")

    def render(self) -> object:
        return Button(self._text, DEFAULT, variant=self._variant, state=self._state)


class PlaygroundApp(App):
    """One screen, bricks and Textual-integrated interaction demos."""

    CSS = """
    Screen { background: #000000; }
    #gallery { padding: 1 2; }
    .row { height: auto; }
    InteractiveButton { width: auto; height: 1; margin-right: 1; }
    """

    BINDINGS: ClassVar = [("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        with Vertical(id="gallery"):
            yield Brick(heading("playground", DEFAULT))
            yield Brick(Text(" "))
            yield Brick(label("interactive (textual-integrated)", DEFAULT))
            with Horizontal(classes="row"):
                yield InteractiveButton("Primary", variant="primary")
                yield InteractiveButton("Secondary", variant="secondary")
                yield InteractiveButton("Ghost", variant="ghost")
                yield InteractiveButton("Danger", variant="danger")
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
