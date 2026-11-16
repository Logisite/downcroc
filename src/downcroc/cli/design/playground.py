"""Playground: the live app for reviewing the design system.

Run ``uv run python -m downcroc.cli.design.playground`` to see the bricks
in a real Textual screen. Headless exports live in gallery.py.

Phase 2 (2.1-2.3): Textual-aligned interaction integration
(events, focus, hover, CSS/pseudo-states) using interaction/* adapters.
"""

from __future__ import annotations

from typing import ClassVar

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widget import Widget

from downcroc.cli.design.docs_ui import DocsShell
from downcroc.cli.design.interaction.scroll import scroll_to_widget, scroll_to_y
from downcroc.cli.design.primitives.card import Card
from downcroc.cli.design.primitives.keybar import keybar
from downcroc.cli.design.primitives.text import heading, label, prose
from downcroc.cli.design.theme import DEFAULT
from downcroc.cli.design.widgets import (
    CopyableCodePanelWidget,
    FocusableCardWidget,
    InteractiveBreadcrumbWidget,
    InteractiveButtonWidget,
    InteractiveKeycapWidget,
    InteractiveLinkWidget,
    InteractiveNavItemWidget,
    InteractivePagerWidget,
    InteractiveTocItemWidget,
    NavListWidget,
    PrimitiveAction,
    SelectableListWidget,
    SelectableTableWidget,
    TocListWidget,
)


class Brick(Widget):
    """Minimal wrapper: renders a Rich renderable inside the app."""

    def __init__(self, renderable: object, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._renderable = renderable

    def render(self) -> object:
        return self._renderable


class ActionLog(Widget):
    """Consumes bubbled PrimitiveAction messages (action layer demo)."""

    DEFAULT_CSS = """
    ActionLog { height: 1; }
    """

    def __init__(self) -> None:
        super().__init__()
        self._last = "actions: (interact to emit)"

    def set_action(self, action) -> None:
        target = f" target={action.target}" if action.target else ""
        payload = f" {action.payload}" if action.payload else ""
        self._last = f"action: {action.kind.value}{target}{payload}"
        self.refresh()

    def render(self) -> object:
        return Text(self._last, style=DEFAULT.style("fg_faint"))


class PlaygroundApp(App):
    """Phase 2 playground: 2.1 interaction base, 2.2 actionable atoms, 2.3 collections."""

    CSS = """
    Screen { background: #000000; }
    #gallery { padding: 1 2; }
    .row { height: auto; }
    .cols { height: auto; }
    .stack { height: auto; }
    InteractiveButtonWidget { width: auto; height: 1; margin-right: 1; }
    InteractiveLinkWidget { width: auto; height: 1; margin-right: 2; }
    InteractiveKeycapWidget { width: auto; height: 1; margin-right: 1; }
    InteractiveNavItemWidget { width: 40; height: 1; }
    InteractiveTocItemWidget { width: 32; height: 1; }
    NavListWidget { width: 40; height: auto; margin-right: 2; }
    TocListWidget { width: 28; height: auto; }
    SelectableListWidget { width: 32; height: auto; margin-right: 2; }
    SelectableTableWidget { width: 44; height: auto; }
    FocusableCardWidget { width: auto; height: auto; margin-right: 1; }
    CopyableCodePanelWidget { width: 72; height: auto; }
    InteractiveBreadcrumbWidget { width: auto; height: 1; }
    InteractivePagerWidget { width: auto; height: auto; }
    ActionLog { height: 1; }
    DocsShell { height: 24; border: round #232330; margin-top: 1; }
    """

    BINDINGS: ClassVar = [("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="gallery"):
            yield Brick(heading("playground — phase 2.1-2.3", DEFAULT))
            yield Brick(
                Text(
                    "Textual events/focus + interaction adapters (state/hover/focus/actions/hit/pointer)",
                    style=DEFAULT.style("fg_muted"),
                )
            )
            yield ActionLog()
            with Horizontal(classes="row", id="scroll-controls"):
                yield InteractiveButtonWidget(
                    "Scroll to code", variant="ghost", target="scroll-code"
                )
                yield InteractiveButtonWidget(
                    "Scroll to top", variant="ghost", target="scroll-top"
                )
            yield Brick(Text(" "))

            yield Brick(
                label("docs-nav foundation: interactive breadcrumb + history", DEFAULT),
                id="section-breadcrumb",
            )
            with Horizontal(classes="row"):
                yield InteractiveBreadcrumbWidget(
                    ["docs", "design", "components", "breadcrumb"],
                    selected=3,
                    id="breadcrumb-demo",
                )
                yield InteractiveButtonWidget(
                    "Back", variant="ghost", target="breadcrumb-back"
                )
            yield Brick(Text(" "))

            yield Brick(
                label(
                    "docs shell scaffold (5-zone, nav/content/outline, scroll-spy/anchors)",
                    DEFAULT,
                )
            )
            yield DocsShell(
                title="Design Docs Shell",
                sections=[
                    (
                        "intro",
                        "Introduction",
                        "Entry point and overview for the docs shell.",
                    ),
                    (
                        "tokens",
                        "Tokens",
                        "Color, spacing, and state token foundations.",
                    ),
                    (
                        "components",
                        "Components",
                        "Primitives and composed layout blocks.",
                    ),
                    (
                        "interaction",
                        "Interaction",
                        "Focus, actions, scroll and outline tracking.",
                    ),
                ],
                id="docs-shell",
            )
            yield Brick(Text(" "))
            yield Brick(
                label("previous/next navigation (interactive, link targets)", DEFAULT)
            )
            yield InteractivePagerWidget(
                prev_label="Tokens",
                prev_target="/docs/design/tokens",
                next_label="Components",
                next_target="/docs/design/components",
                width=72,
                id="pager-demo",
            )
            yield Brick(Text(" "))

            yield Brick(
                label("2.2 actionable atoms: buttons / link / keycap", DEFAULT),
                id="section-atoms",
            )
            with Horizontal(classes="row"):
                yield InteractiveButtonWidget("Primary", variant="primary")
                yield InteractiveButtonWidget("Secondary", variant="secondary")
                yield InteractiveButtonWidget("Ghost", variant="ghost")
                yield InteractiveButtonWidget("Danger", variant="danger")
            with Horizontal(classes="row"):
                yield InteractiveLinkWidget(
                    "Docs link", href="https://example.com/docs"
                )
                yield InteractiveLinkWidget("Plain link")
                yield InteractiveKeycapWidget("enter")
                yield InteractiveKeycapWidget("space")
                yield InteractiveKeycapWidget("tab")
            yield Brick(Text(" "))

            yield Brick(
                label("2.3 standalone nav/toc items (focus/hover/select)", DEFAULT)
            )
            with Horizontal(classes="cols"):
                with Vertical(classes="stack"):
                    yield InteractiveNavItemWidget(
                        "Inbox", icon="inbox", active=True, badge_text="12"
                    )
                    yield InteractiveNavItemWidget("Sent", icon="sent")
                    yield InteractiveNavItemWidget("Archive", icon="folder")
                with Vertical(classes="stack"):
                    yield InteractiveTocItemWidget("Overview", active=True)
                    yield InteractiveTocItemWidget("Tokens", level=2)
                    yield InteractiveTocItemWidget("Interactions", level=2)
            yield Brick(Text(" "))

            yield Brick(
                label("2.3 collection interaction (nav/toc/list/table)", DEFAULT)
            )
            with Horizontal(classes="cols"):
                yield NavListWidget(
                    [
                        ("Inbox", {"icon": "inbox", "badge": "12"}),
                        ("Sent", {"icon": "sent"}),
                        ("Archive", {"icon": "folder", "indent": 1}),
                        ("Trash", {"icon": "folder"}),
                    ],
                    selected=0,
                )
                yield TocListWidget(
                    [("Overview", 1), ("Setup", 1), ("Tokens", 2), ("State", 2)],
                    selected=1,
                )
            with Horizontal(classes="cols"):
                yield SelectableListWidget(
                    ["Queued message", "Sync worker", "Retry policy", "Audit trail"],
                    selected=0,
                )
                yield SelectableTableWidget(
                    ["Service", "State", "Jobs"],
                    [
                        ["ingest", "ok", "2"],
                        ["send", "warn", "1"],
                        ["sync", "idle", "0"],
                        ["audit", "ok", "4"],
                    ],
                    width=42,
                    selected=1,
                )
            yield Brick(Text(" "))

            yield Brick(label("2.3 focusable/selectable cards", DEFAULT))
            with Horizontal(classes="row"):
                yield FocusableCardWidget(
                    "watcher",
                    "Focus/click to select; hover/focus/selected states.",
                    DEFAULT,
                    width=36,
                )
                yield FocusableCardWidget(
                    "sync",
                    "Focusable card with hairline treatment.",
                    DEFAULT,
                    width=34,
                    border="hairline",
                )
            yield Brick(Text(" "))

            yield Brick(
                label("2.2 code panel (precise copy hit-target + actions)", DEFAULT)
            )
            yield CopyableCodePanelWidget(id="code-demo")
            yield Brick(Text(" "))

            yield Brick(label("static reference", DEFAULT))
            yield Brick(
                prose("Body text from the fg scale, never pure white.", DEFAULT)
            )
            yield Brick(
                Card("static", "Static card for comparison.", DEFAULT, width=40)
            )
            yield Brick(Text(" "))
            yield Brick(
                keybar(
                    [
                        ("tab", "focus"),
                        ("↑↓", "select"),
                        ("enter/space", "activate/copy"),
                        ("q", "quit"),
                    ],
                    DEFAULT,
                )
            )

    def on_primitive_action(self, message: PrimitiveAction) -> None:
        log = self.query_one(ActionLog)
        log.set_action(message.action)
        action = message.action
        if action.target == "scroll-code" and action.kind.value in {
            "tapped",
            "activated",
        }:
            container = self.query_one("#gallery", VerticalScroll)
            scroll_to_widget(container, self.query_one("#code-demo"))
        elif action.target == "scroll-top" and action.kind.value in {
            "tapped",
            "activated",
        }:
            container = self.query_one("#gallery", VerticalScroll)
            scroll_to_y(container, 0)
        elif action.target == "breadcrumb-back" and action.kind.value in {
            "tapped",
            "activated",
        }:
            crumb = self.query_one("#breadcrumb-demo", InteractiveBreadcrumbWidget)
            crumb.go_back()


def run() -> None:
    PlaygroundApp().run()


if __name__ == "__main__":
    run()
