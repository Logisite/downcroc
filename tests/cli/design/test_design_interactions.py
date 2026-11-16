"""Phase 2 interaction tests: Textual-aligned events/focus/actions/collections."""

from __future__ import annotations

import asyncio

from textual.app import App, ComposeResult
from textual.widgets import Static

from downcroc.cli.design.interaction.actions import ActionKind
from downcroc.cli.design.widgets import (
    CopyableCodePanelWidget,
    InteractiveBreadcrumbWidget,
    InteractiveButtonWidget,
    NavListWidget,
    PrimitiveAction,
    SelectableListWidget,
    SelectableTableWidget,
)


class _ActionCapture(Static):
    def __init__(self, **kwargs) -> None:
        super().__init__("", **kwargs)
        self.actions = []

    def record(self, action) -> None:
        self.actions.append(action)
        self.update(f"{action.kind.value}:{action.target}")


class ButtonApp(App):
    def compose(self) -> ComposeResult:
        yield InteractiveButtonWidget("Go", variant="primary", id="btn")
        yield _ActionCapture(id="log")

    def on_primitive_action(self, message: PrimitiveAction) -> None:
        self.query_one(_ActionCapture).record(message.action)


class NavApp(App):
    def compose(self) -> ComposeResult:
        yield NavListWidget(
            [("Inbox", {"icon": "inbox"}), ("Sent", {"icon": "sent"}), ("Trash", {})],
            selected=0,
            id="nav",
        )
        yield _ActionCapture(id="log")

    def on_primitive_action(self, message: PrimitiveAction) -> None:
        self.query_one(_ActionCapture).record(message.action)


class ListTableApp(App):
    def compose(self) -> ComposeResult:
        yield SelectableListWidget(["a", "b", "c"], selected=0, id="list")
        yield SelectableTableWidget(
            ["Name", "State"],
            [["one", "ok"], ["two", "warn"], ["three", "idle"]],
            selected=0,
            id="table",
        )


def test_button_emits_actions_and_focus_state() -> None:
    async def run() -> None:
        app = ButtonApp()
        async with app.run_test() as pilot:
            btn = app.query_one(InteractiveButtonWidget)
            log = app.query_one(_ActionCapture)
            await pilot.click(InteractiveButtonWidget)
            await pilot.pause()
            assert btn._state.value in {"focus", "hover"}
            assert any(a.kind == ActionKind.PRESSED for a in log.actions)
            assert any(a.kind == ActionKind.TAPPED for a in log.actions)
            await pilot.press("enter")
            await pilot.pause()
            assert any(a.kind == ActionKind.ACTIVATED for a in log.actions)

    asyncio.run(run())


def test_nav_collection_keyboard_selection() -> None:
    async def run() -> None:
        app = NavApp()
        async with app.run_test() as pilot:
            nav = app.query_one(NavListWidget)
            log = app.query_one(_ActionCapture)
            nav.focus()
            await pilot.pause()
            assert nav._selected == 0
            await pilot.press("down")
            await pilot.pause()
            assert nav._selected == 1
            assert any(a.kind == ActionKind.SELECTED for a in log.actions)
            await pilot.press("enter")
            await pilot.pause()
            assert any(a.kind == ActionKind.ACTIVATED for a in log.actions)

    asyncio.run(run())


def test_list_and_table_keyboard_selection() -> None:
    async def run() -> None:
        app = ListTableApp()
        async with app.run_test() as pilot:
            lst = app.query_one(SelectableListWidget)
            tbl = app.query_one(SelectableTableWidget)
            lst.focus()
            await pilot.pause()
            assert lst._selected == 0
            await pilot.press("down")
            await pilot.pause()
            assert lst._selected == 1
            tbl.focus()
            await pilot.pause()
            assert tbl._selected == 0
            await pilot.press("down")
            await pilot.pause()
            assert tbl._selected == 1
            await pilot.press("enter")
            await pilot.pause()
            assert tbl._selected == 1

    asyncio.run(run())


def test_code_panel_copy_action_via_keyboard() -> None:
    class CodeApp(App):
        def compose(self) -> ComposeResult:
            yield CopyableCodePanelWidget(id="code")
            yield _ActionCapture(id="log")

        def on_primitive_action(self, message: PrimitiveAction) -> None:
            self.query_one(_ActionCapture).record(message.action)

    async def run() -> None:
        app = CodeApp()
        async with app.run_test() as pilot:
            code = app.query_one(CopyableCodePanelWidget)
            log = app.query_one(_ActionCapture)
            code.focus()
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert any(a.kind == ActionKind.COPIED for a in log.actions)

    asyncio.run(run())


def test_breadcrumb_keyboard_and_click_selection() -> None:
    class BreadcrumbApp(App):
        def compose(self) -> ComposeResult:
            yield InteractiveBreadcrumbWidget(
                ["docs", "design", "components"], id="crumbs", selected=2
            )
            yield _ActionCapture(id="log")

        def on_primitive_action(self, message: PrimitiveAction) -> None:
            self.query_one(_ActionCapture).record(message.action)

    async def run() -> None:
        app = BreadcrumbApp()
        async with app.run_test() as pilot:
            crumbs = app.query_one(InteractiveBreadcrumbWidget)
            log = app.query_one(_ActionCapture)
            crumbs.focus()
            await pilot.pause()
            assert crumbs._selected == 2
            await pilot.press("left")
            await pilot.pause()
            assert crumbs._selected == 1
            assert any(
                a.kind == ActionKind.SELECTED and a.payload.get("label") == "design"
                for a in log.actions
            )
            await pilot.press("enter")
            await pilot.pause()
            assert any(
                a.kind == ActionKind.ACTIVATED and a.payload.get("label") == "design"
                for a in log.actions
            )
            # click first segment ("docs" at x=0)
            await pilot.click(InteractiveBreadcrumbWidget, offset=(1, 0))
            await pilot.pause()
            assert crumbs._selected == 0
            assert any(
                a.kind == ActionKind.SELECTED and a.payload.get("label") == "docs"
                for a in log.actions
            )

    asyncio.run(run())


def test_pager_keyboard_activation() -> None:
    from downcroc.cli.design.widgets import InteractivePagerWidget

    class PagerApp(App):
        def compose(self) -> ComposeResult:
            yield InteractivePagerWidget(
                prev_label="Tokens",
                prev_target="/docs/tokens",
                next_label="Components",
                next_target="/docs/components",
                id="pager",
            )
            yield _ActionCapture(id="log")

        def on_primitive_action(self, message: PrimitiveAction) -> None:
            self.query_one(_ActionCapture).record(message.action)

    async def run() -> None:
        app = PagerApp()
        async with app.run_test() as pilot:
            pager = app.query_one(InteractivePagerWidget)
            log = app.query_one(_ActionCapture)
            pager.focus()
            await pilot.pause()
            await pilot.press("right")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert any(
                a.kind == ActionKind.ACTIVATED and a.payload.get("side") == "next"
                for a in log.actions
            )
            assert any(
                a.payload.get("target") == "/docs/components" for a in log.actions
            )

    asyncio.run(run())
