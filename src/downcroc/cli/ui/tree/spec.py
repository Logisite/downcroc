from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Any

GLOBAL_DESTS = frozenset(
    {
        "json",
        "no_input",
        "yes",
        "wide",
        "full",
        "glyphs",
        "color",
        "quiet",
        "timeout",
        "no_pager",
    }
)

POSITIONAL = "positional"
BOOL = "bool"
VALUE = "value"
CHOICE = "choice"
MULTI = "multi"
PAIR = "pair"


@dataclass(frozen=True)
class ArgSpec:
    dest: str
    flags: tuple[str, ...]
    help: str
    kind: str
    required: bool = False
    nargs: str | None = None
    choices: tuple[str, ...] = ()
    default: Any = None
    metavar: str = ""
    type_name: str = ""
    global_option: bool = False

    @property
    def flag(self) -> str:
        return self.flags[0] if self.flags else self.dest

    @property
    def repeatable(self) -> bool:
        return self.kind == MULTI

    def label(self) -> str:
        if not self.flags:
            return self.dest
        return " / ".join(self.flags)


@dataclass(frozen=True)
class CommandSpec:
    path: tuple[str, ...]
    help: str
    description: str
    args: tuple[ArgSpec, ...]
    children: tuple[CommandSpec, ...]

    @property
    def leaf(self) -> bool:
        return not self.children

    @property
    def runnable(self) -> bool:
        return bool(self.args) or self.leaf or not self.path

    @property
    def positionals(self) -> tuple[ArgSpec, ...]:
        return tuple(arg for arg in self.args if arg.kind == POSITIONAL)

    @property
    def options(self) -> tuple[ArgSpec, ...]:
        return tuple(arg for arg in self.args if arg.kind != POSITIONAL)

    def find(self, path: tuple[str, ...]) -> CommandSpec | None:
        if not path:
            return self
        head, *tail = path
        for child in self.children:
            if child.path[-1] == head:
                return child.find(tuple(tail))
        return None


@dataclass(frozen=True)
class Tree:
    root: CommandSpec
    globals: tuple[ArgSpec, ...]


def build_tree(parser: argparse.ArgumentParser) -> Tree:
    globals_ = _global_specs(parser)
    root = _walk(parser, (), "", globals_)
    return Tree(root=root, globals=globals_)


def _walk(
    parser: argparse.ArgumentParser,
    path: tuple[str, ...],
    help_text: str,
    globals_: tuple[ArgSpec, ...],
) -> CommandSpec:
    subparsers = _subparsers(parser)
    labels = _choice_help(subparsers)
    children = tuple(
        _walk(child, (*path, name), labels.get(name, ""), globals_)
        for name, child in (subparsers.choices.items() if subparsers else ())
    )
    args = tuple(_arg_specs(parser, globals_))
    return CommandSpec(
        path=path,
        help=help_text,
        description=parser.description or "",
        args=args,
        children=children,
    )


def _subparsers(
    parser: argparse.ArgumentParser,
) -> argparse._SubParsersAction | None:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action
    return None


def _choice_help(
    subparsers: argparse._SubParsersAction | None,
) -> dict[str, str]:
    if subparsers is None:
        return {}
    return {
        str(choice.dest): str(choice.help or "")
        for choice in subparsers._choices_actions
    }


def _global_specs(parser: argparse.ArgumentParser) -> tuple[ArgSpec, ...]:
    return tuple(
        spec
        for action in parser._actions
        if action.dest in GLOBAL_DESTS
        for spec in [_spec(action, global_option=True)]
        if spec is not None
    )


def _arg_specs(
    parser: argparse.ArgumentParser,
    globals_: tuple[ArgSpec, ...],
) -> list[ArgSpec]:
    del globals_
    consumed: set[int] = set()
    specs: list[ArgSpec] = []
    for group in parser._mutually_exclusive_groups:
        pair = _pair(group)
        if pair is not None:
            consumed.update(id(action) for action in group._group_actions)
            specs.append(pair)
    for action in parser._actions:
        if id(action) in consumed:
            continue
        if action.dest in GLOBAL_DESTS:
            continue
        spec = _spec(action)
        if spec is not None:
            specs.append(spec)
    return specs


def _pair(group: argparse._MutuallyExclusiveGroup) -> ArgSpec | None:
    actions = list(group._group_actions)
    if len(actions) < 2:
        return None
    if not all(
        isinstance(action, (argparse._StoreTrueAction, argparse._StoreFalseAction))
        for action in actions
    ):
        return None
    flags = tuple(
        flag
        for action in actions
        for flag in action.option_strings
        if flag not in ("-h", "--help")
    )
    dests = {action.dest for action in actions}
    dest = dests.pop() if len(dests) == 1 else f"pair:{flags[0]}"
    return ArgSpec(
        dest=dest,
        flags=flags,
        help=" / ".join(str(action.help or "") for action in actions),
        kind=PAIR,
        default=None,
    )


def _spec(action: argparse.Action, *, global_option: bool = False) -> ArgSpec | None:
    if isinstance(
        action,
        (argparse._HelpAction, argparse._VersionAction, argparse._SubParsersAction),
    ):
        return None
    if action.dest in ("help", "version"):
        return None
    flags = tuple(
        flag for flag in action.option_strings if flag not in ("-h", "--help")
    )
    positional = not action.option_strings
    if not positional and not flags:
        return None
    kind = _kind(action, positional)
    choices = tuple(str(choice) for choice in action.choices or ())
    default = None if action.default is argparse.SUPPRESS else action.default
    return ArgSpec(
        dest=action.dest,
        flags=flags,
        help=str(action.help or ""),
        kind=kind,
        required=_required(action, positional),
        nargs=action.nargs,
        choices=choices,
        default=default,
        metavar=str(action.metavar or action.dest),
        type_name=_type_name(action),
        global_option=global_option,
    )


def _kind(action: argparse.Action, positional: bool) -> str:
    if positional:
        return MULTI if action.nargs in ("+", "*") else POSITIONAL
    if isinstance(action, (argparse._StoreTrueAction, argparse._StoreFalseAction)):
        return BOOL
    if isinstance(action, argparse._AppendAction) or action.nargs in ("+", "*"):
        return MULTI
    if action.choices:
        return CHOICE
    return VALUE


def _required(action: argparse.Action, positional: bool) -> bool:
    if positional:
        return action.nargs not in ("?", "*")
    return bool(action.required)


def _type_name(action: argparse.Action) -> str:
    if action.type is None:
        return "text"
    return getattr(action.type, "__name__", "text")
