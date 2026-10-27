from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from downcroc.cli.errors import Cancelled, CliError, render
from downcroc.cli.ui.prompts import Option, ask, choose, confirm
from downcroc.cli.ui.session import Ui

ACTION = "\x00action"


class Quit(Exception):
    """Leave the interactive menu."""


def quit_menu() -> None:
    raise Quit()


@dataclass
class Item:
    label: str
    detail: str = ""
    badge: str = ""
    action: Callable[[], object] | None = None
    children: list[Item] = field(default_factory=list)

    def option(self) -> Option:
        return Option(
            label=self.label, value=self, detail=self.detail, badge=self.badge
        )


def render_header(ui: Ui, lines: list[str]) -> None:
    if ui.quiet:
        return
    for line in lines:
        print(line)
    print()


def menu(ui: Ui, title: str, items: list[Item], *, back: bool = True) -> Item | None:
    if not ui.interactive:
        return None
    chosen = choose(
        title,
        [item.option() for item in items],
        ui=ui,
        back=back,
    )
    if chosen is None:
        return None
    return chosen  # type: ignore[return-value]


def run_args(ui: Ui, *argv: str) -> int:
    from downcroc.cli import dispatch

    try:
        return dispatch.run(list(argv))
    except CliError as error:
        render(error, json_mode=ui.json_mode)
        return error.exit_code
    except Cancelled:
        print(ui.dim("cancelled"))
        return 1


def run(ui: Ui, title: str, items: list[Item], *, breadcrumb: str = "") -> None:
    stack: list[tuple[str, list[Item]]] = [(title, items)]
    try:
        while stack:
            current_title, current_items = stack[-1]
            heading = f"{breadcrumb} / {current_title}".strip(" /")
            selected = menu(ui, heading, current_items, back=True)
            if selected is None:
                stack.pop()
                continue
            if selected.children:
                stack.append((selected.label, selected.children))
                continue
            if selected.action is None:
                stack.pop()
                continue
            try:
                selected.action()
            except Cancelled:
                return
            except Quit:
                return
    except Quit:
        return


def pick(ui: Ui, title: str, items: list[Item]) -> Item | None:
    return menu(ui, title, items)


def open_menu(ui: Ui, name: str) -> bool:
    """Open a named interactive menu. Returns False when there is no terminal."""
    if not ui.interactive:
        return False
    from downcroc.cli.ui import menus, menus_work

    renderer = getattr(menus, name, None) or getattr(menus_work, name, None)
    if renderer is None:
        return False
    renderer(ui)
    return True


def free_text(
    ui: Ui,
    label: str,
    *,
    default: str | None = None,
    required: bool = True,
    field: str | None = None,
) -> str:
    return ask(label, ui=ui, default=default, required=required, field=field)


def yes(ui: Ui, question: str, *, default: bool = False) -> bool:
    return confirm(question, ui=ui, default=default)


def count_label(count: int, noun: str) -> str:
    suffix = "" if count == 1 else "s"
    return f"{count:,} {noun}{suffix}"
