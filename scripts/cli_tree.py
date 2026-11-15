"""Print the downcroc CLI tree for any command path.

Usage:
    uv run python scripts/cli_tree.py                       # whole tree
    uv run python scripts/cli_tree.py account               # from a command
    uv run python scripts/cli_tree.py account archive       # from a subcommand
    uv run python scripts/cli_tree.py batch --depth 2       # limit depth
    uv run python scripts/cli_tree.py batch --no-flags      # commands only
    uv run python scripts/cli_tree.py jobs --help-text      # include help

Useful when updating documentation: render the tree and compare it with
what the docs claim, so the two never drift apart.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from rich.console import Console
from rich.text import Text

from downcroc.cli.parser import build_parser

COMMAND = "bold cyan"
SUBCOMMAND = "bold green"
FLAG = "yellow"
CHOICE = "magenta"
ARGUMENT = "bright_blue"
HELP = "dim"
BRANCH_BAD = "bold red"


def subparsers_of(parser: Any) -> dict[str, Any]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return dict(action.choices)
    return {}


COMMON_FLAGS = {
    "json",
    "no_input",
    "wide",
    "full",
    "glyphs",
    "color",
    "quiet",
    "timeout",
    "no_pager",
    "yes",
}


def split_flags(parser: Any, help_text: bool) -> tuple[list[Text], Text | None]:
    """Return (specific flags, one collapsed line for the global set)."""
    specific: list[Text] = []
    common: list[str] = []
    for action in parser._actions:
        if isinstance(
            action,
            (argparse._HelpAction, argparse._VersionAction, argparse._SubParsersAction),
        ):
            continue
        if not action.option_strings:
            continue
        names = "/".join(action.option_strings)
        if action.choices:
            names += " {" + "|".join(str(c) for c in action.choices) + "}"
        elif not isinstance(action, argparse._StoreTrueAction):
            names += f" <{action.metavar or action.dest}>"
        if action.dest in COMMON_FLAGS:
            common.append("/".join(action.option_strings))
            continue
        line = Text(names, style=FLAG)
        if help_text and action.help:
            line.append("  " + str(action.help), style=HELP)
        specific.append(line)
    collapsed = None
    if common:
        collapsed = Text(
            "common: " + " ".join(common),
            style=HELP,
        )
    return specific, collapsed


def positionals_of(parser: Any) -> list[Text]:
    out = []
    for action in parser._actions:
        if action.option_strings:
            continue
        if isinstance(
            action,
            (argparse._HelpAction, argparse._VersionAction, argparse._SubParsersAction),
        ):
            continue
        repeat = "..." if action.nargs in ("+", "*") else ""
        out.append(Text(f"{action.dest}{repeat}", style=ARGUMENT))
    return out


def build(
    parser: Any,
    label: str,
    *,
    show_flags: bool,
    help_text: bool,
    depth: int,
) -> Any:
    kind = "command" if subparsers_of(parser) else "leaf"
    root_label = Text(label, style=SUBCOMMAND if depth else COMMAND)
    for positional in positionals_of(parser):
        root_label.append(" ")
        root_label.append(positional)
    if show_flags:
        specific, collapsed = split_flags(parser, help_text)
        for flag in specific:
            root_label.append("\n")
            root_label.append(Text("  ", style=HELP))
            root_label.append(flag)
        if collapsed is not None:
            root_label.append("\n")
            root_label.append(Text("  ", style=HELP))
            root_label.append(collapsed)
    if help_text and parser.description:
        root_label.append("\n")
        root_label.append(Text(f"  {parser.description}", style=HELP))
    from rich.tree import Tree

    node = Tree(root_label, guide_style="dim")
    if depth <= 0:
        subs = subparsers_of(parser)
        if subs and kind == "command":
            hint = Text("... (raise --depth to see subcommands)", style=HELP)
            node.add(hint)
        return node
    for name, sub in subparsers_of(parser).items():
        child = build(
            sub,
            name,
            show_flags=show_flags,
            help_text=help_text,
            depth=depth - 1,
        )
        node.add(child)
    return node


def resolve(words: list[str]) -> tuple[Any, str]:
    parser: Any = build_parser()
    label = "downcroc"
    for word in words:
        subs = subparsers_of(parser)
        if word not in subs:
            hint = ", ".join(sorted(subs)) or "(no subcommands)"
            raise SystemExit(f"unknown command {word!r} under {label}; choices: {hint}")
        parser = subs[word]
        label = f"{label} {word}"
    return parser, label


def main() -> int:
    arg_parser = argparse.ArgumentParser(
        description="print the downcroc CLI tree from any command path",
    )
    arg_parser.add_argument(
        "path",
        nargs="*",
        help="command path, for example: account archive",
    )
    arg_parser.add_argument(
        "--depth",
        type=int,
        default=99,
        help="levels of subcommands to expand (default: all)",
    )
    arg_parser.add_argument(
        "--no-flags",
        action="store_true",
        help="hide flags, show only commands",
    )
    arg_parser.add_argument(
        "--help-text",
        action="store_true",
        help="include the help string of each item",
    )
    args = arg_parser.parse_args()

    parser, label = resolve(args.path)
    tree = build(
        parser,
        label,
        show_flags=not args.no_flags,
        help_text=args.help_text,
        depth=args.depth,
    )
    console = Console(force_terminal=True)
    console.print(tree)
    return 0


if __name__ == "__main__":
    sys.exit(main())
