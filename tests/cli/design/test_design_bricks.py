"""Design system bricks: golden-image and color tests.

The snapshot is the design gate: if a token or paint call drifts, the
screenshot diff catches it. Color math is verified directly since it is pure.
"""

from __future__ import annotations

import pytest
from syrupy.extensions.image import PNGImageSnapshotExtension  # noqa: F401

from downcroc.cli.design.gallery import (
    export_gallery_plain_text,
    export_gallery_text,
)
from downcroc.cli.design.paint.color import blend, gradient
from downcroc.cli.design.playground import PlaygroundApp

pytestmark = pytest.mark.usefixtures("snap_compare")


def test_blend_interpolates() -> None:
    assert blend("#000000", "#ffffff", 0.5) == "#808080"
    assert blend("#0b0e14", "#0b0e14", 0.7) == "#0b0e14"


def test_gradient_colors_each_glyph() -> None:
    out = gradient("ab", "#000000", "#ffffff")
    assert "#000000" in out and "#ffffff" in out


def test_gallery_text_renders_bricks() -> None:
    text = export_gallery_text()
    assert "downcroc design system" in text
    assert "watcher" in text
    assert "enter" in text
    assert "BUTTON STATES (PRIMARY)" in text
    assert "CALLOUT TONES" in text
    assert "NAV ITEMS / STATES" in text
    assert "No data yet" in text
    assert "disabled copy state" in text
    assert "copied state" in text
    assert "Figure: compact inset panel sample" in text
    assert "caption and sections" in text
    assert "service health" in text
    assert "snapshot" in text
    assert "prose tones" in text
    assert "account rows" in text
    assert "stacked with divider" in text
    assert "Compact warning" in text
    assert "Example" in text
    assert "Search returned nothing" in text
    assert "italic" in text
    assert "strike" in text
    assert "narrow / ellipsis" in text
    assert "full-width aligned divider" in text
    assert "truncate end" in text
    assert "truncate middle" in text
    assert "truncate start" in text
    assert "row styles (state tones)" in text
    assert "typed row states (dict api)" in text
    assert "fixed rule width" in text
    assert "long values (aligned)" in text
    assert "content-width divider" in text
    assert "BUTTON STATE MATRIX" in text
    assert "compact toasts" in text
    assert "focus copy state" in text
    assert "Custom icon" in text
    assert "No icon" in text
    assert "Inset panel with extra padding" in text
    assert "empty (no header)" in text
    plain = export_gallery_plain_text()
    assert "hovered" in plain
    assert "audit" in plain
    assert "selected" in plain
    assert "No rows" in plain
    assert "docs › reference › design › primitives › table" in plain
    assert "runtime/se…ecycle.py" in plain
    assert "…runtime.lifecycle" in plain
    assert "A short quoted note without citation." in text


def test_gallery_plain_text_snapshot(snapshot) -> None:
    """Stable text snapshot of the full gallery structure/content."""
    assert export_gallery_plain_text() == snapshot


def test_text_primitives_targeted(snapshot) -> None:
    """Targeted text primitive variants/states snapshot."""
    from io import StringIO

    from rich.console import Console

    from downcroc.cli.design.primitives.text import breadcrumb, truncate
    from downcroc.cli.design.theme import DEFAULT

    console = Console(
        record=True, width=60, force_terminal=False, color_system=None, file=StringIO()
    )
    console.print(truncate("a very long identifier name", 18, mode="end"))
    console.print(truncate("runtime/service/lifecycle.py", 20, mode="middle"))
    console.print(truncate("downcroc.runtime.lifecycle", 18, mode="start"))
    console.print(breadcrumb(["docs", "design", "table"], DEFAULT))
    console.print(
        breadcrumb(
            [("docs", "default"), ("design", "hover"), ("table", "focus")], DEFAULT
        )
    )
    assert console.export_text() == snapshot


def test_table_and_key_value_targeted(snapshot) -> None:
    """Targeted table/key-value edge cases snapshot."""
    from io import StringIO

    from rich.console import Console

    from downcroc.cli.design.primitives.key_value import KeyValue
    from downcroc.cli.design.primitives.table_view import TableView
    from downcroc.cli.design.theme import DEFAULT

    console = Console(
        record=True, width=60, force_terminal=False, color_system=None, file=StringIO()
    )
    console.print(
        TableView(
            ["Check", "Result"],
            [
                (["lint", "ok"], False, f"{DEFAULT.success} on {DEFAULT.success_dim}"),
                (
                    ["tests", "failed"],
                    False,
                    f"{DEFAULT.danger} on {DEFAULT.danger_dim}",
                ),
                (
                    ["sync", "selected"],
                    False,
                    f"{DEFAULT.accent_strong} on {DEFAULT.bg_selected}",
                ),
            ],
            DEFAULT,
            zebra=False,
            show_lines=False,
        )
    )
    console.print(
        TableView(
            ["Item", "State"],
            [
                {"cells": ["build", "ok"], "style": "success"},
                {"cells": ["deploy", "selected"], "style": "selected"},
                {"cells": ["audit", "danger"], "style": "danger"},
            ],
            DEFAULT,
            zebra=False,
            compact=True,
        )
    )
    console.print(
        TableView(
            ["Field", "Value", "State"],
            [],
            DEFAULT,
            compact=True,
            empty_text="No data yet",
            show_header_on_empty=True,
        )
    )
    console.print(TableView([], [], DEFAULT))
    console.print(
        KeyValue(
            [("queue", "12"), ("workers", "3")],
            DEFAULT,
            divider=True,
            rule_width=24,
            compact=True,
        )
    )
    console.print(
        KeyValue(
            [("id", "a1"), ("region", "eu-west-1")], DEFAULT, divider=True, compact=True
        )
    )
    assert console.export_text() == snapshot


def test_feedback_primitives_targeted(snapshot) -> None:
    """Targeted feedback/nav/code/button states snapshot."""
    from io import StringIO

    from rich.console import Console

    from downcroc.cli.design.primitives.button import Button
    from downcroc.cli.design.primitives.callout import Callout
    from downcroc.cli.design.primitives.code_panel import CodePanel
    from downcroc.cli.design.primitives.nav import NavItem, TocItem
    from downcroc.cli.design.primitives.toast import Toast
    from downcroc.cli.design.theme import DEFAULT

    console = Console(
        record=True, width=70, force_terminal=False, color_system=None, file=StringIO()
    )
    console.print(Button("Send", DEFAULT, variant="primary", state="focus"))
    console.print(Button("Delete", DEFAULT, variant="danger", state="disabled"))
    console.print(Callout("Note", "Compact body", DEFAULT, compact=True, width=40))
    console.print(Toast("Saved", DEFAULT, tone="success", compact=True))
    console.print(NavItem("Inbox", DEFAULT, icon="inbox", active=True, width=30))
    console.print(NavItem("Drafts", DEFAULT, icon="folder", state="hover", width=30))
    console.print(TocItem("Setup", DEFAULT, level=2, state="focus"))
    console.print(
        CodePanel(
            "echo hi\n",
            DEFAULT,
            language="bash",
            filename="x.sh",
            width=40,
            button_state="focus",
        )
    )
    assert console.export_text() == snapshot


def test_surfaces_targeted(snapshot) -> None:
    """Targeted panel/callout rhythm snapshot."""
    from io import StringIO

    from rich.console import Console

    from downcroc.cli.design.primitives.callout import Callout
    from downcroc.cli.design.primitives.panel import Panel
    from downcroc.cli.design.theme import DEFAULT

    console = Console(
        record=True, width=50, force_terminal=False, color_system=None, file=StringIO()
    )
    console.print(Panel("Token padded panel", DEFAULT, width=30, padding=2))
    console.print(
        Callout(
            "Tip",
            "Body uses tokenized indent spacing.",
            DEFAULT,
            tone="tip",
            width=40,
            compact=True,
        )
    )
    assert console.export_text() == snapshot


def test_lists_and_structure_targeted(snapshot) -> None:
    """Targeted list/blockquote/tag rhythm snapshot."""
    from io import StringIO

    from rich.console import Console

    from downcroc.cli.design.primitives.blockquote import Blockquote
    from downcroc.cli.design.primitives.list_block import ListBlock
    from downcroc.cli.design.primitives.tag_list import TagList
    from downcroc.cli.design.theme import DEFAULT

    console = Console(
        record=True, width=50, force_terminal=False, color_system=None, file=StringIO()
    )
    console.print(
        ListBlock(
            [("Parent", 0, None), ("Child item", 1, None), ("Second", 0, None)],
            DEFAULT,
        )
    )
    console.print(Blockquote("Quoted text", DEFAULT, cite="ref"))
    console.print(TagList(["one", "two", "three"], DEFAULT))
    assert console.export_text() == snapshot


def test_components_rhythm_targeted(snapshot) -> None:
    """Targeted badge/rule/section/button rhythm snapshot."""
    from io import StringIO

    from rich.console import Console

    from downcroc.cli.design.primitives.badge import badge
    from downcroc.cli.design.primitives.button import Button
    from downcroc.cli.design.primitives.rule import divider, hairline
    from downcroc.cli.design.primitives.section_header import SectionHeader
    from downcroc.cli.design.theme import DEFAULT

    console = Console(
        record=True, width=50, force_terminal=False, color_system=None, file=StringIO()
    )
    console.print(badge("info", DEFAULT, tone="info"))
    console.print(badge("warn", DEFAULT, tone="warning", variant="outline"))
    console.print(hairline(DEFAULT, width=20))
    console.print(divider(DEFAULT, width=30, label="group"))
    console.print(SectionHeader("Details", DEFAULT, meta="meta"))
    console.print(Button("Save", DEFAULT, variant="secondary", state="focus"))
    assert console.export_text() == snapshot


def test_content_primitives_targeted(snapshot) -> None:
    """Targeted code/figure/empty/callout snapshot."""
    from io import StringIO

    from rich.console import Console

    from downcroc.cli.design.primitives.callout import Callout
    from downcroc.cli.design.primitives.code_panel import CodePanel
    from downcroc.cli.design.primitives.empty_state import EmptyState
    from downcroc.cli.design.primitives.figure import Figure
    from downcroc.cli.design.primitives.panel import Panel
    from downcroc.cli.design.theme import DEFAULT

    console = Console(
        record=True, width=60, force_terminal=False, color_system=None, file=StringIO()
    )
    console.print(Figure(Panel("fig", DEFAULT, width=20), DEFAULT, caption="cap"))
    console.print(EmptyState("Empty", DEFAULT, body="none", hint="do x", compact=True))
    console.print(Callout("Info", "Body", DEFAULT, tone="info", compact=True, width=30))
    console.print(
        CodePanel(
            "print(1)\n",
            DEFAULT,
            language="python",
            filename="a.py",
            width=30,
            button_state="hover",
        )
    )
    assert console.export_text() == snapshot


def test_navigation_targeted(snapshot) -> None:
    """Targeted nav/toc/keybar/icon rhythm snapshot."""
    from io import StringIO

    from rich.console import Console

    from downcroc.cli.design.primitives.icon import icon, status_dot
    from downcroc.cli.design.primitives.keybar import keybar, keycap
    from downcroc.cli.design.primitives.nav import NavItem, TocItem
    from downcroc.cli.design.theme import DEFAULT

    console = Console(
        record=True, width=50, force_terminal=False, color_system=None, file=StringIO()
    )
    console.print(NavItem("Inbox", DEFAULT, icon="inbox", active=True, width=30))
    console.print(NavItem("Archive", DEFAULT, icon="folder", indent=1, width=30))
    console.print(TocItem("Intro", DEFAULT, active=True))
    console.print(TocItem("Details", DEFAULT, level=2))
    console.print(icon("search", DEFAULT))
    console.print(status_dot(DEFAULT, tone="success"))
    console.print(keycap("enter", DEFAULT))
    console.print(keybar([("q", "quit"), ("?", "help")], DEFAULT))
    assert console.export_text() == snapshot


@pytest.mark.parametrize("path_to_cli", [[], None])
def test_playground_snapshot(snap_compare: object, path_to_cli: list) -> None:
    assert snap_compare(PlaygroundApp(), terminal_size=(90, 22))
