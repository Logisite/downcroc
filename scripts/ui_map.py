"""Map the interactive CLI: menus, editor fields, and the key grammar.

This is the truth source for the book's interactive chapters, the way
``cli_tree.py`` is the truth source for the typed CLI. Everything it prints
comes from the real tree the interactive session walks.

Usage:
    uv run python scripts/ui_map.py                     # the whole map
    uv run python scripts/ui_map.py job create          # from a leaf
    uv run python scripts/ui_map.py account             # from a menu
    uv run python scripts/ui_map.py job create --md     # markdown fragment
    uv run python scripts/ui_map.py --json > /tmp/ui.json
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from rich.console import Console
from rich.text import Text

from downcroc.cli.parser import build_parser
from downcroc.cli.ui.tree.session import _entries, _submenu, _title
from downcroc.cli.ui.tree.spec import ArgSpec, CommandSpec, Tree, build_tree

MENU = "bold cyan"
ENTRY = "bold green"
FIELD = "yellow"
GLOBAL = "magenta"
RUN = "bright_green"
DETAIL = "dim"

KEYS = {
    "menu": "↑↓ move · enter choose · o options · b back · q quit",
    "editor": "↑↓ move · enter edit · x clear · b back · r run · q quit",
    "pick": "↑↓ move · enter choose · / filter · b back",
    "confirm": "y yes · n no",
}


def resolve(words: list[str]) -> tuple[CommandSpec, Tree, str]:
    from downcroc.cli.ui.tree.session import _choice_exposure

    tree = build_tree(build_parser())
    node = tree.root
    label = "downcroc"
    for word in words:
        children = {child.path[-1]: child for child in node.children}
        if word in children:
            node = children[word]
            label = f"{label} {word}"
            continue
        choices = _choice_exposure(node)
        if choices and word in choices.choices:
            return node, tree, f"{label} {word}"
        hint_items = sorted(children)
        if choices:
            hint_items = sorted(choices.choices)
        hint = ", ".join(hint_items) or "(no subcommands)"
        raise SystemExit(f"unknown command {word!r} under {label}; choices: {hint}")
    return node, tree, label


def kind_label(spec: ArgSpec) -> str:
    if spec.kind == "bool":
        return "yes/no"
    if spec.choices:
        return "one of " + " / ".join(spec.choices)
    if spec.kind == "multi":
        return "list; repeat the field to add more"
    return "text"


def fields_of(
    spec: CommandSpec, globals_spec: tuple[ArgSpec, ...]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    own = [
        {
            "field": spec_arg.label(),
            "kind": kind_label(spec_arg),
            "required": bool(spec_arg.required),
            "default": spec_arg.default if spec_arg.kind == "bool" else None,
        }
        for spec_arg in (*spec.positionals, *spec.options)
    ]
    global_fields = [
        {"field": spec_arg.label(), "kind": kind_label(spec_arg)}
        for spec_arg in globals_spec
    ]
    return own, global_fields


def entries_of(node: CommandSpec) -> list[dict[str, Any]]:
    out = []
    for entry in _entries(node):
        child_path = "/".join(entry.node.path) if entry.node else None
        out.append(
            {
                "label": entry.label,
                "detail": entry.detail,
                "run": entry.run,
                "fields": entry.count,
                "path": child_path,
            }
        )
    return out


def map_of(node: CommandSpec, tree: Tree, label: str) -> dict[str, Any]:
    is_menu = _submenu(node)
    data: dict[str, Any] = {"path": label, "title": _title(node)}
    if is_menu:
        data["kind"] = "menu"
        data["keys"] = KEYS["menu"]
        data["entries"] = entries_of(node)
    else:
        own, global_fields = fields_of(node, tree.globals)
        data["kind"] = "editor"
        data["keys"] = KEYS["editor"]
        data["fields"] = own
        data["common_fields"] = global_fields
        if (
            node.positionals
            and len(node.positionals) == 1
            and node.positionals[0].choices
        ):
            data["note"] = (
                "this screen is presented as a menu of "
                f"{len(node.positionals[0].choices)} choices"
            )
    return data


def render_text(data: dict[str, Any]) -> Text:
    text = Text(data["title"], style=MENU)
    text.append(f"\n  {data['kind']}", style=DETAIL)
    text.append("\n  keys: ", style=DETAIL)
    text.append(data["keys"], style=RUN)
    if data["kind"] == "menu":
        for entry in data["entries"]:
            text.append("\n  ├─ ")
            text.append(entry["label"], style=RUN if entry["run"] else ENTRY)
            if entry["fields"]:
                text.append(f"  ({entry['fields']} fields)", style=DETAIL)
            if entry["detail"]:
                text.append(f"  {entry['detail']}", style=DETAIL)
    else:
        for field_row in data["fields"]:
            text.append("\n  ├─ ")
            text.append(field_row["field"], style=FIELD)
            text.append(f"  {field_row['kind']}", style=DETAIL)
            if field_row["required"]:
                text.append("  required", style=DETAIL)
            if field_row["default"] is True:
                text.append("  on by default", style=DETAIL)
        for field_row in data["common_fields"]:
            text.append("\n  ├─ ")
            text.append(field_row["field"], style=GLOBAL)
            text.append("  (common to every screen)", style=DETAIL)
        if data.get("note"):
            text.append("\n  ")
            text.append(data["note"], style=DETAIL)
    return text


def render_md(data: dict[str, Any]) -> str:
    lines = [f"screen: {data['title']} ({data['kind']})", f"keys: {data['keys']}"]
    if data["kind"] == "menu":
        for entry in data["entries"]:
            if entry["run"]:
                marker = "run"
            elif entry["fields"]:
                marker = "opens fields"
            else:
                marker = "opens screen"
            suffix = f", {entry['fields']} fields" if entry["fields"] else ""
            detail = f": {entry['detail']}" if entry["detail"] else ""
            lines.append(f"- {entry['label']} ({marker}{suffix}){detail}")
    else:
        for field_row in data["fields"]:
            marks = []
            if field_row["required"]:
                marks.append("required")
            if field_row["default"] is True:
                marks.append("on by default")
            extra = f" [{', '.join(marks)}]" if marks else ""
            lines.append(f"- {field_row['field']}: {field_row['kind']}{extra}")
        lines.append(
            f"- common: {', '.join(f['field'] for f in data['common_fields'])}"
        )
        if data.get("note"):
            lines.append(f"- note: {data['note']}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="map the interactive cli: menus, fields, keys",
    )
    parser.add_argument("path", nargs="*", help="command path, e.g. job create")
    parser.add_argument("--md", action="store_true", help="markdown fragment")
    parser.add_argument("--json", action="store_true", help="machine-readable")
    args = parser.parse_args()

    node, tree, label = resolve(args.path)
    data = map_of(node, tree, label)
    if args.json:
        print(json.dumps(data, indent=2))
    elif args.md:
        print(render_md(data))
    else:
        console = Console(force_terminal=True)
        console.print(render_text(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
