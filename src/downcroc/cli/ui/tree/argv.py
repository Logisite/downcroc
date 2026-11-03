from __future__ import annotations

import shlex
from dataclasses import dataclass

from downcroc.cli.ui.tree.spec import BOOL, MULTI, PAIR, ArgSpec, CommandSpec
from downcroc.cli.ui.tree.state import Globals, LeafState


@dataclass(frozen=True)
class Missing:
    arg: ArgSpec
    reason: str


def global_argv(globals: Globals) -> list[str]:
    argv: list[str] = []
    if globals.json:
        argv.append("--json")
    if globals.no_input:
        argv.append("--no-input")
    if globals.yes:
        argv.append("--yes")
    if globals.wide:
        argv.append("--wide")
    if globals.full:
        argv.append("--full")
    if globals.glyphs and globals.glyphs != "auto":
        argv.extend(["--glyphs", globals.glyphs])
    if globals.color and globals.color != "auto":
        argv.extend(["--color", globals.color])
    if globals.quiet:
        argv.append("--quiet")
    if globals.timeout is not None:
        argv.extend(["--timeout", _number(globals.timeout)])
    if globals.no_pager:
        argv.append("--no-pager")
    return argv


def compose(spec: CommandSpec, state: LeafState, globals: Globals) -> list[str]:
    argv = global_argv(globals)
    argv.extend(spec.path)
    for arg in spec.positionals:
        value = state.get(arg.dest)
        if value in (None, "", []):
            continue
        argv.extend(_values(value))
    for arg in spec.options:
        value = state.get(arg.dest)
        if value in (None, "", []):
            continue
        if arg.kind == BOOL:
            if value:
                argv.append(arg.flag)
        elif arg.kind == PAIR:
            argv.append(str(value))
        elif arg.kind == MULTI:
            for item in _values(value):
                argv.extend([arg.flag, item])
        else:
            argv.extend([arg.flag, str(value)])
    return argv


def missing(spec: CommandSpec, state: LeafState) -> list[Missing]:
    found: list[Missing] = []
    for arg in spec.positionals:
        if arg.required and state.get(arg.dest) in (None, "", []):
            found.append(Missing(arg, "a value is required"))
    for arg in spec.options:
        if arg.required and state.get(arg.dest) in (None, "", []):
            found.append(Missing(arg, "this option is required"))
    return found


def preview(argv: list[str]) -> list[str]:
    if not argv:
        return ["downcroc"]
    return shlex.join(["downcroc", *argv]).splitlines()


def _values(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)
