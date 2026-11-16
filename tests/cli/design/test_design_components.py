"""Phase 3 composite bricks: built from primitives, no domain coupling."""

from __future__ import annotations

from io import StringIO

from rich.console import Console

from downcroc.cli.design.components.breadcrumb_bar import BreadcrumbBar
from downcroc.cli.design.components.callout_group import CalloutGroup
from downcroc.cli.design.components.code_group import CodeGroup
from downcroc.cli.design.components.figure_block import FigureBlock
from downcroc.cli.design.components.hero import Hero
from downcroc.cli.design.components.meta_bar import MetaBar
from downcroc.cli.design.components.meta_rows import MetaRows
from downcroc.cli.design.components.nav_group import NavGroup
from downcroc.cli.design.components.page_header import PageHeader
from downcroc.cli.design.components.pager import Pager
from downcroc.cli.design.components.section import Section
from downcroc.cli.design.gallery import export_gallery_plain_text
from downcroc.cli.design.primitives.callout import Callout
from downcroc.cli.design.primitives.code_panel import CodePanel
from downcroc.cli.design.primitives.key_value import KeyValue
from downcroc.cli.design.theme import DEFAULT


def test_gallery_includes_composites() -> None:
    plain = export_gallery_plain_text()
    assert "Composites (Phase 3)" in plain
    assert "Docs page" in plain
    assert "primitive-first" in plain
    assert "NAVIGATION GROUP" in plain
    assert "Code group" in plain
    assert "Callouts" in plain
    assert "BREADCRUMB BAR" in plain
    assert "updated:" in plain
    assert "phase:" in plain
    assert "PAGER (PREVIOUS/NEXT)" in plain
    assert "Tokens" in plain
    assert "Components" in plain
    assert "Meta rows" in plain
    assert "Figure: panel wrapped as a figure composite" in plain


def test_page_header_composite(snapshot) -> None:
    console = Console(
        record=True, width=60, force_terminal=False, color_system=None, file=StringIO()
    )
    console.print(
        PageHeader(
            "Page title",
            DEFAULT,
            subtitle="Lead text composed from primitives.",
            meta="meta: sample",
            width=54,
        )
    )
    assert console.export_text() == snapshot


def test_hero_composite(snapshot) -> None:
    console = Console(
        record=True, width=64, force_terminal=False, color_system=None, file=StringIO()
    )
    console.print(
        Hero(
            "Hero title",
            "Lead paragraph for the hero block.",
            DEFAULT,
            width=60,
            highlight_title="highlight",
            highlight_body="Composed from card + text.",
        )
    )
    assert console.export_text() == snapshot


def test_section_and_nav_group_composites(snapshot) -> None:
    console = Console(
        record=True, width=50, force_terminal=False, color_system=None, file=StringIO()
    )
    console.print(
        Section(
            "Details",
            KeyValue([("a", "1"), ("b", "2")], DEFAULT, divider=True, compact=True),
            DEFAULT,
            meta="meta",
        )
    )
    console.print(
        NavGroup(
            "Group",
            [
                ("One", {"icon": "inbox", "active": True}),
                ("Two", {"icon": "folder", "state": "hover"}),
                ("Three", {"icon": "folder", "indent": 1}),
            ],
            DEFAULT,
            width=36,
        )
    )
    assert console.export_text() == snapshot


def test_code_and_callout_group_composites(snapshot) -> None:
    console = Console(
        record=True, width=60, force_terminal=False, color_system=None, file=StringIO()
    )
    console.print(
        CodeGroup(
            "Examples",
            [
                CodePanel(
                    "echo hi", DEFAULT, language="bash", filename="a.sh", width=50
                ),
                CodePanel(
                    "print('x')",
                    DEFAULT,
                    language="python",
                    filename="b.py",
                    width=50,
                    button_state="hover",
                ),
            ],
            DEFAULT,
            meta="meta",
        )
    )
    console.print(
        CalloutGroup(
            "Notes",
            [
                Callout("Info", "Body", DEFAULT, tone="info", width=50),
                Callout(
                    "Warn",
                    "Careful",
                    DEFAULT,
                    tone="warning",
                    width=50,
                    compact=True,
                ),
            ],
            DEFAULT,
            meta="meta",
        )
    )
    assert console.export_text() == snapshot


def test_breadcrumb_bar_and_meta_bar_composites(snapshot) -> None:
    console = Console(
        record=True, width=64, force_terminal=False, color_system=None, file=StringIO()
    )
    console.print(
        BreadcrumbBar(
            [("docs", "default"), ("design", "hover"), ("components", "active")],
            DEFAULT,
            title="Path",
        )
    )
    console.print(
        MetaBar(
            [("author", "docs"), ("updated", "2026-11-16"), ("phase", "3")],
            DEFAULT,
        )
    )
    assert console.export_text() == snapshot


def test_pager_composite(snapshot) -> None:
    console = Console(
        record=True, width=72, force_terminal=False, color_system=None, file=StringIO()
    )
    console.print(
        Pager(
            DEFAULT,
            prev_label="Tokens",
            prev_target="/docs/tokens",
            next_label="Components",
            next_target="/docs/components",
            width=68,
            next_state="hover",
        )
    )
    assert console.export_text() == snapshot


def test_meta_rows_and_figure_block_composites(snapshot) -> None:
    from downcroc.cli.design.primitives.panel import Panel

    console = Console(
        record=True, width=60, force_terminal=False, color_system=None, file=StringIO()
    )
    console.print(
        MetaRows(
            "Details",
            [("a", "1"), ("b", "2"), ("c", "3")],
            DEFAULT,
            width=40,
        )
    )
    console.print(
        FigureBlock(
            Panel("content", DEFAULT, width=30, fill="bg_inset"),
            "caption text",
            DEFAULT,
        )
    )
    assert console.export_text() == snapshot
