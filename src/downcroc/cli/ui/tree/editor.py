from __future__ import annotations

from dataclasses import dataclass

from downcroc.cli.errors import Cancelled
from downcroc.cli.ui import ansi, panel, prompts
from downcroc.cli.ui.frame import Frame
from downcroc.cli.ui.frame import rows as terminal_rows
from downcroc.cli.ui.keys import (
    CTRL_C,
    CTRL_D,
    DOWN,
    END,
    ENTER,
    ESC,
    HOME,
    SPACE,
    UP,
    Keys,
)
from downcroc.cli.ui.session import Ui
from downcroc.cli.ui.tree import unlock
from downcroc.cli.ui.tree.argv import compose, preview
from downcroc.cli.ui.tree.execute import execute
from downcroc.cli.ui.tree.spec import BOOL, MULTI, PAIR, ArgSpec, CommandSpec
from downcroc.cli.ui.tree.state import Globals, LeafState
from downcroc.cli.ui.tree.values import Named, has_resolver, match, resolve

LABEL_MAX = 24
MANUAL = object()
CLEAR = object()
EMPTY = (None, "", [])


@dataclass(frozen=True)
class Row:
    scope: str
    arg: ArgSpec
    group: str


def edit(
    ui: Ui,
    spec: CommandSpec,
    state: LeafState,
    globals: Globals,
    globals_spec: tuple[ArgSpec, ...],
) -> str:
    entries = _rows(spec, globals_spec)
    if not entries:
        return "back"
    cursor = 0
    last: tuple[int, str] | None = None
    with Keys() as keys, Frame(ui) as frame:
        while True:
            body, cursor_line, head, tail = _body(
                ui, spec, entries, cursor, state, globals, last
            )
            lines = _window(ui, body, cursor_line, head, tail)
            frame.draw(panel.frame(ui, _panel_title(spec), lines))
            key = keys.read()
            if key in (CTRL_C, CTRL_D, ESC, "b", "B"):
                return "back"
            if key in ("q", "Q"):
                return "quit"
            if key in (UP, "k"):
                cursor = max(0, cursor - 1)
                continue
            if key in (DOWN, "j"):
                cursor = min(len(entries) - 1, cursor + 1)
                continue
            if key == HOME:
                cursor = 0
                continue
            if key == END:
                cursor = len(entries) - 1
                continue
            if key == "x":
                state.clear()
                last = None
                continue
            if key == "r":
                if spec.children:
                    last = (2, "choose a command first")
                    continue
                try:
                    require(ui, spec, state, globals)
                except Cancelled:
                    continue
                frame.erase()
                with keys.cooked():
                    code, message, _, error_code = execute(spec, state, globals)
                    if unlock.is_locked(error_code, message):
                        outcome = unlock.offer(ui)
                        if outcome is not None:
                            last = (
                                (0, "vault unlocked")
                                if outcome
                                else (1, "vault unlock failed")
                            )
                            continue
                last = (code, message)
                continue
            if key in (ENTER, SPACE):
                row = entries[cursor]
                frame.erase()
                if key == SPACE and row.arg.kind == BOOL:
                    _toggle(row, state, globals)
                else:
                    _edit_row(ui, spec, row, state, globals)
            elif isinstance(key, str) and key.isdigit() and key != "0":
                spot = int(key) - 1
                if spot < len(entries):
                    cursor = spot


def _panel_title(spec: CommandSpec) -> str:
    if not spec.path:
        return "downcroc"
    return "downcroc / " + " / ".join(part.replace("_", " ") for part in spec.path)


def _rows(spec: CommandSpec, globals_spec: tuple[ArgSpec, ...]) -> list[Row]:
    entries = [Row("arg", arg, "Arguments") for arg in spec.positionals]
    entries.extend(Row("arg", arg, "Options") for arg in spec.options)
    entries.extend(Row("global", arg, "Global options") for arg in globals_spec)
    return entries


def require(
    ui: Ui,
    spec: CommandSpec,
    state: LeafState,
    globals: Globals,
) -> None:
    for arg in spec.positionals:
        if state.get(arg.dest) not in EMPTY:
            continue
        row = Row("arg", arg, "Arguments")
        if has_resolver(spec.path, arg.dest):
            _pick(ui, spec, row, state, globals)
        elif arg.required:
            _text(ui, spec, row, state, globals)
    for arg in spec.options:
        if state.get(arg.dest) not in EMPTY or not arg.required:
            continue
        row = Row("arg", arg, "Options")
        if has_resolver(spec.path, arg.dest):
            _pick(ui, spec, row, state, globals)
        else:
            _text(ui, spec, row, state, globals)


def _body(
    ui: Ui,
    spec: CommandSpec,
    entries: list[Row],
    cursor: int,
    state: LeafState,
    globals: Globals,
    last: tuple[int, str] | None,
) -> tuple[list[str], int, int, int]:
    limit = panel.content_width(ui)
    width = min(
        max((ansi.cells(entry.arg.label()) for entry in entries), default=8),
        LABEL_MAX,
    )
    head = [ui.accent("Command")]
    for line in preview(compose(spec, state, globals)):
        head.append(ui.dim(ansi.fit("  " + line, limit)))
    if last is not None:
        head.extend(["", _result(ui, last)])
    body: list[str] = []
    cursor_line = 0
    section = ""
    for index, entry in enumerate(entries):
        if entry.group != section:
            if body:
                if entry.group == "Global options":
                    body.append(ui.dim("\u2500" * limit))
                else:
                    body.append("")
            body.append(ui.accent(entry.group))
            section = entry.group
        if index == cursor:
            cursor_line = len(body)
        body.append(_line(ui, entry, index == cursor, state, globals, width, limit))
    body.extend(["", ui.dim(ansi.fit(_HINT, limit))])
    tail = len(body) - len(entries) - 1
    return [*head, *body], cursor_line, len(head), tail


_HINT = "space toggle   enter edit   r run   x reset   b back   q quit"


def _window(
    ui: Ui,
    body: list[str],
    cursor_line: int,
    head: int,
    tail: int,
) -> list[str]:
    available = max(6, terminal_rows(ui) - 14)
    if len(body) <= available:
        return body
    room = max(3, available - head - tail)
    middle = body[head : len(body) - tail]
    if len(middle) <= room:
        return body
    at = max(0, cursor_line - head)
    start = max(0, min(at - room // 2, len(middle) - room))
    shown = middle[start : start + room]
    if start:
        shown.insert(0, ui.dim("  more above"))
    if start + room < len(middle):
        shown.append(ui.dim("  more below"))
    return [*body[:head], *shown, *body[len(body) - tail :]]


def _line(
    ui: Ui,
    entry: Row,
    active: bool,
    state: LeafState,
    globals: Globals,
    width: int,
    limit: int,
) -> str:
    pointer = ui.accent(ui.glyph("pointer")) if active else " "
    prefix = ""
    value = _value(entry, state, globals)
    if entry.arg.kind == BOOL:
        current = _current(entry, state, globals)
        prefix = ui.glyph("checked" if current else "unchecked") + " "
    label = ansi.clip(entry.arg.label(), width)
    label = ui.bold(label) if active else label
    text = f"  {pointer} {prefix}{ansi.pad(label, width)}  {value}"
    room = limit - ansi.cells(text) - 4
    if entry.arg.help and room > 8:
        text += "  " + ui.dim(ansi.clip(entry.arg.help, room))
    return ansi.fit(text.rstrip(), limit)


def _value(entry: Row, state: LeafState, globals: Globals) -> str:
    arg = entry.arg
    value = globals.get(arg.dest) if entry.scope == "global" else state.get(arg.dest)
    if arg.kind == BOOL:
        return ""
    if value in EMPTY:
        return "(required)" if arg.required else "unset"
    if arg.kind == MULTI:
        items = value if isinstance(value, list) else [value]
        return "  ".join(str(item) for item in items)
    if arg.kind == PAIR:
        return str(value)
    label = "" if entry.scope == "global" else state.labels.get(arg.dest, "")
    return label or str(value)


def _result(ui: Ui, last: tuple[int, str]) -> str:
    code, message = last
    return ui.result(code == 0, f"exit {code}", message)


def _toggle(entry: Row, state: LeafState, globals: Globals) -> None:
    current = _current(entry, state, globals)
    value = not bool(current)
    if entry.scope == "global":
        globals.set(entry.arg.dest, value)
    else:
        state.set(entry.arg.dest, value)


def _edit_row(
    ui: Ui,
    spec: CommandSpec,
    entry: Row,
    state: LeafState,
    globals: Globals,
) -> None:
    arg = entry.arg
    if arg.kind == BOOL:
        _toggle(entry, state, globals)
    elif arg.kind == PAIR:
        _choose_pair(ui, spec, entry, state, globals)
    elif arg.kind == MULTI and arg.choices:
        _choose_many(ui, spec, entry, state, globals)
    elif has_resolver(spec.path, arg.dest):
        _pick(ui, spec, entry, state, globals)
    elif arg.choices:
        _choose(ui, spec, entry, state, globals)
    else:
        _text(ui, spec, entry, state, globals)


def _set(
    entry: Row, state: LeafState, globals: Globals, value, label: str = ""
) -> None:
    if entry.scope == "global":
        globals.set(entry.arg.dest, value)
    else:
        state.set(entry.arg.dest, value, label)


def _current(entry: Row, state: LeafState, globals: Globals):
    if entry.scope == "global":
        return globals.get(entry.arg.dest)
    return state.get(entry.arg.dest)


def _title(spec: CommandSpec, entry: Row) -> str:
    name = spec.path[-1] if spec.path else "downcroc"
    return f"{name} / {entry.arg.label()}"


def _choose(
    ui: Ui,
    spec: CommandSpec,
    entry: Row,
    state: LeafState,
    globals: Globals,
) -> None:
    options = [prompts.Option(choice, choice, "") for choice in entry.arg.choices]
    if not entry.arg.required:
        options.append(prompts.Option("Clear", CLEAR, "remove this option"))
    chosen = prompts.choose(_title(spec, entry), options, ui=ui)
    if chosen is not None:
        _set(entry, state, globals, None if chosen is CLEAR else chosen)


def _choose_pair(
    ui: Ui,
    spec: CommandSpec,
    entry: Row,
    state: LeafState,
    globals: Globals,
) -> None:
    options = [prompts.Option(flag, flag, "") for flag in entry.arg.flags]
    options.append(prompts.Option("Clear", CLEAR, "leave both unset"))
    chosen = prompts.choose(_title(spec, entry), options, ui=ui)
    if chosen is not None:
        _set(entry, state, globals, None if chosen is CLEAR else chosen)


def _choose_many(
    ui: Ui,
    spec: CommandSpec,
    entry: Row,
    state: LeafState,
    globals: Globals,
) -> None:
    options = [prompts.Option(choice, choice, "") for choice in entry.arg.choices]
    chosen = prompts.choose_many(_title(spec, entry), options, ui=ui)
    _set(entry, state, globals, [str(item) for item in chosen])


def _pick(
    ui: Ui,
    spec: CommandSpec,
    entry: Row,
    state: LeafState,
    globals: Globals,
) -> None:
    found = resolve(ui, spec.path, entry.arg.dest, state)
    options = [prompts.Option(item.label, item, item.detail) for item in found]
    options.append(prompts.Option("Type a value", MANUAL, "not in the list"))
    if not entry.arg.required:
        options.append(prompts.Option("Clear", CLEAR, "remove this option"))
    chosen = prompts.choose(_title(spec, entry), options, ui=ui)
    if chosen is None:
        return
    if chosen is CLEAR:
        _set(entry, state, globals, None)
    elif chosen is MANUAL:
        _manual(ui, spec, entry, state, globals, found)
    elif isinstance(chosen, Named):
        _set(entry, state, globals, chosen.value, chosen.label)


def _manual(
    ui: Ui,
    spec: CommandSpec,
    entry: Row,
    state: LeafState,
    globals: Globals,
    found: list[Named],
) -> None:
    del spec
    current = _current(entry, state, globals)
    default = None if current in EMPTY else str(current)
    answer = prompts.ask(
        entry.arg.label(),
        ui=ui,
        default=default,
        required=entry.arg.required,
        field=entry.arg.label(),
    )
    named = match(found, answer)
    if named is None:
        _set(entry, state, globals, answer)
    else:
        _set(entry, state, globals, named.value, named.label)


def _text(
    ui: Ui,
    spec: CommandSpec,
    entry: Row,
    state: LeafState,
    globals: Globals,
) -> None:
    del spec
    current = _current(entry, state, globals)
    default: str | None = None
    if entry.arg.kind == MULTI and isinstance(current, list):
        default = ", ".join(str(item) for item in current)
    elif current not in EMPTY:
        default = str(current)
    answer = prompts.ask(
        entry.arg.label(),
        ui=ui,
        default=default,
        required=entry.arg.required,
        field=entry.arg.label(),
    )
    if entry.arg.kind == MULTI:
        parts = [part.strip() for part in answer.split(",") if part.strip()]
        _set(entry, state, globals, parts)
    else:
        _set(entry, state, globals, answer or None)
