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
    assert "fixed rule width" in text
    assert "compact toasts" in text
    assert "focus copy state" in text
    plain = export_gallery_plain_text()
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
            ],
            DEFAULT,
            zebra=False,
            show_lines=False,
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
    console.print(
        KeyValue(
            [("queue", "12"), ("workers", "3")],
            DEFAULT,
            divider=True,
            rule_width=24,
            compact=True,
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


@pytest.mark.parametrize("path_to_cli", [[], None])
def test_playground_snapshot(snap_compare: object, path_to_cli: list) -> None:
    assert snap_compare(PlaygroundApp(), terminal_size=(90, 22))
