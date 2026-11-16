"""Phase 1 closure: comprehensive per-primitive edge-case targeted snapshots."""

from __future__ import annotations

from io import StringIO

from rich.columns import Columns
from rich.console import Console, Group
from rich.text import Text

from downcroc.cli.design.gallery import export_gallery_plain_text
from downcroc.cli.design.primitives.badge import badge
from downcroc.cli.design.primitives.blockquote import Blockquote
from downcroc.cli.design.primitives.button import Button
from downcroc.cli.design.primitives.callout import Callout
from downcroc.cli.design.primitives.card import Card
from downcroc.cli.design.primitives.empty_state import EmptyState
from downcroc.cli.design.primitives.figure import Figure
from downcroc.cli.design.primitives.icon import icon, status_dot
from downcroc.cli.design.primitives.key_value import KeyValue
from downcroc.cli.design.primitives.keybar import keybar, keycap
from downcroc.cli.design.primitives.list_block import ListBlock
from downcroc.cli.design.primitives.nav import NavItem, TocItem
from downcroc.cli.design.primitives.panel import Panel
from downcroc.cli.design.primitives.rule import divider, hairline
from downcroc.cli.design.primitives.section_header import SectionHeader
from downcroc.cli.design.primitives.table_view import TableView
from downcroc.cli.design.primitives.tag_list import TagList
from downcroc.cli.design.primitives.text import (
    breadcrumb,
    chip,
    heading,
    inline_code,
    italic,
    label,
    link_text,
    muted,
    prose,
    strike,
    strong,
    truncate,
)
from downcroc.cli.design.primitives.toast import Toast
from downcroc.cli.design.theme import DEFAULT


def _console(width: int = 60) -> Console:
    return Console(
        record=True,
        width=width,
        force_terminal=False,
        color_system=None,
        file=StringIO(),
    )


def test_gallery_phase1_edge_markers() -> None:
    plain = export_gallery_plain_text()
    assert "typed row states (dict api)" in plain
    assert "content-width divider" in plain
    assert "single column / alignments" in plain
    assert "single item / no divider" in plain
    assert "Custom icon toast" in plain
    assert "truncate narrow middle" in plain
    assert "hovered" in plain
    assert "audit" in plain
    assert "No icon" in plain


def test_text_edge_targeted(snapshot) -> None:
    console = _console(60)
    inline = Text()
    inline.append_text(strong("strong", DEFAULT))
    inline.append(" ")
    inline.append_text(italic("italic", DEFAULT))
    inline.append(" ")
    inline.append_text(strike("strike", DEFAULT))
    inline.append(" ")
    inline.append_text(muted("muted", DEFAULT))
    inline.append(" ")
    inline.append_text(chip("chip", DEFAULT))
    inline.append(" ")
    inline.append_text(inline_code("code", DEFAULT))
    console.print(
        Group(
            heading("H1", DEFAULT, level=1),
            heading("H2", DEFAULT, level=2),
            heading("H3", DEFAULT, level=3),
            label("section", DEFAULT),
            label("faint", DEFAULT, tone="fg_faint"),
            prose(
                "Wrapped prose text for edge coverage and rhythm.", DEFAULT, width=34
            ),
            prose("Muted prose", DEFAULT, width=20, tone="fg_muted"),
            inline,
            link_text("default", DEFAULT),
            link_text("hover", DEFAULT, state="hover"),
            link_text("focus", DEFAULT, state="focus"),
            Text("end:" + truncate("abcdefghijklmnop", 8)),
            Text("mid:" + truncate("abcdefghijklmnop", 8, mode="middle")),
            Text("start:" + truncate("abcdefghijklmnop", 8, mode="start")),
            Text("tiny:" + truncate("abc", 1)),
            breadcrumb(["a", "b", "c"], DEFAULT),
            breadcrumb([("a", "default"), ("b", "hover"), ("c", "active")], DEFAULT),
        )
    )
    assert console.export_text() == snapshot


def test_badge_rule_section_edge_targeted(snapshot) -> None:
    console = _console(50)
    console.print(badge("info", DEFAULT, tone="info"))
    console.print(badge("warn", DEFAULT, tone="warning", variant="solid"))
    console.print(badge("err", DEFAULT, tone="danger", variant="outline"))
    console.print(badge("ok", DEFAULT, tone="success", variant="subtle"))
    console.print(hairline(DEFAULT, width=20))
    console.print(divider(DEFAULT, width=30, label="group"))
    console.print(SectionHeader("Details", DEFAULT, meta="meta"))
    console.print(SectionHeader("Only title", DEFAULT))
    assert console.export_text() == snapshot


def test_surfaces_edge_targeted(snapshot) -> None:
    console = _console(50)
    console.print(
        Group(
            Card("t", "body text", DEFAULT, width=24),
            Card("h", "hairline body", DEFAULT, width=24, border="hairline"),
            Panel("panel", DEFAULT, width=20),
            Panel("padded", DEFAULT, width=20, fill="bg_inset", padding=2),
            Panel("zero", DEFAULT, width=16, padding=0),
            Figure(Panel("fig", DEFAULT, width=14), DEFAULT, caption="cap"),
            Blockquote("quoted", DEFAULT, width=28),
            Blockquote("quoted cite", DEFAULT, cite="src", width=28),
        )
    )
    assert console.export_text() == snapshot


def test_callout_toast_edge_targeted(snapshot) -> None:
    console = _console(56)
    for tone in ["note", "tip", "warning", "danger", "info", "success"]:
        console.print(Callout(tone, f"{tone} body", DEFAULT, tone=tone, width=42))
    console.print(Callout("No icon", "body", DEFAULT, icon="", compact=True, width=42))
    console.print(
        Callout("Custom", "body", DEFAULT, icon="search", compact=True, width=42)
    )
    for tone in ["info", "success", "warning", "danger"]:
        console.print(Toast(f"{tone} toast", DEFAULT, tone=tone))
        console.print(Toast(f"{tone} compact", DEFAULT, tone=tone, compact=True))
    console.print(
        Toast("Custom icon toast", DEFAULT, tone="info", icon="search", compact=True)
    )
    assert console.export_text() == snapshot


def test_button_edge_targeted(snapshot) -> None:
    console = _console(80)
    for variant in ["primary", "secondary", "ghost", "danger"]:
        row = [
            Button("Btn", DEFAULT, variant=variant, state=s)
            for s in ["default", "hover", "focus", "pressed", "disabled"]
        ]
        console.print(Columns(row, expand=False, padding=(0, 1)))
    console.print(Button("Search", DEFAULT, variant="secondary", icon="search"))
    assert console.export_text() == snapshot


def test_nav_toc_icon_tag_keybar_edge_targeted(snapshot) -> None:
    console = _console(60)
    console.print(NavItem("Active", DEFAULT, icon="inbox", active=True, width=30))
    console.print(NavItem("Hover", DEFAULT, icon="folder", state="hover", width=30))
    console.print(NavItem("Focus", DEFAULT, icon="settings", state="focus", width=30))
    console.print(
        NavItem(
            "Disabled",
            DEFAULT,
            icon="folder",
            state="disabled",
            width=30,
            badge_text="2",
        )
    )
    console.print(TocItem("Active", DEFAULT, active=True))
    console.print(TocItem("Hover", DEFAULT, state="hover"))
    console.print(TocItem("Focus", DEFAULT, level=2, state="focus"))
    console.print(icon("search", DEFAULT))
    console.print(status_dot(DEFAULT, tone="success"))
    console.print(status_dot(DEFAULT, tone="danger"))
    console.print(TagList(["a", "bb", "ccc"], DEFAULT))
    console.print(TagList(["single"], DEFAULT))
    console.print(keycap("enter", DEFAULT))
    console.print(keybar([("q", "quit"), ("?", "help")], DEFAULT))
    assert console.export_text() == snapshot


def test_list_empty_edge_targeted(snapshot) -> None:
    console = _console(50)
    console.print(ListBlock(["one", "two"], DEFAULT))
    console.print(ListBlock(["first", "second"], DEFAULT, ordered=True))
    console.print(ListBlock([("parent", 0), ("child", 1), ("leaf", 2)], DEFAULT))
    console.print(ListBlock(["todo", "done"], DEFAULT, task=True))
    console.print(EmptyState("Empty", DEFAULT))
    console.print(
        EmptyState(
            "None", DEFAULT, body="body", hint="hint", icon="inbox", compact=True
        )
    )
    console.print(
        EmptyState(
            "Search returned nothing", DEFAULT, body="Try broader query.", compact=True
        )
    )
    assert console.export_text() == snapshot


def test_table_kv_edge_targeted(snapshot) -> None:
    console = _console(64)
    console.print(
        TableView(
            ["A", "B", "C"],
            [["1", "2", "3"], ["4", "5", "6"]],
            DEFAULT,
            align=["left", "right", "center"],
            compact=True,
            zebra=False,
        )
    )
    console.print(
        TableView(
            ["Item", "State"],
            [
                {"cells": ["x", "hover"], "style": "hover"},
                {"cells": ["y", "focus"], "style": "focus"},
                {"cells": ["z", "danger"], "style": "danger", "end_section": True},
                {"cells": ["w", "selected"], "style": "selected"},
            ],
            DEFAULT,
            compact=True,
            zebra=False,
        )
    )
    console.print(
        TableView(["X", "Y"], [], DEFAULT, show_header_on_empty=True, empty_text="None")
    )
    console.print(TableView([], [], DEFAULT))
    console.print(KeyValue([("k", "v")], DEFAULT, compact=True))
    console.print(KeyValue([("k", "v")], DEFAULT, divider=True, compact=True))
    console.print(
        KeyValue(
            [("long-key-name", "long value text here")],
            DEFAULT,
            divider=True,
            width=42,
            compact=True,
        )
    )
    console.print(
        KeyValue(
            [("mailbox_path", "INBOX/Projects/downcroc/design")],
            DEFAULT,
            key_width=14,
            divider=True,
            width=58,
            compact=True,
        )
    )
    console.print(
        KeyValue([("a", "1"), ("b", "2")], DEFAULT, stacked=True, divider=True)
    )
    assert console.export_text() == snapshot
