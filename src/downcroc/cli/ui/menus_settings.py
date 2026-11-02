from __future__ import annotations

import json
from typing import Any

from downcroc.cli.client import api, get
from downcroc.cli.context import load
from downcroc.cli.errors import CliError, render
from downcroc.cli.output import flatten
from downcroc.cli.ui import prompts
from downcroc.cli.ui.data import action
from downcroc.cli.ui.menu import Item, quit_menu, run, run_args
from downcroc.cli.ui.session import Ui

NUMBERS = {"integer", "number"}


def _state(ui: Ui) -> tuple[dict[str, Any], list[dict]] | None:
    paths, _, _ = load()
    try:
        with api(paths) as client:
            document = get(client, "/api/config")
            schema = get(client, "/api/config/schema")
    except CliError as error:
        render(error, json_mode=ui.json_mode)
        return None
    return document, schema["fields"]


def _rules(field: dict) -> str:
    values = field.get("values") or []
    if values:
        return "one of " + ", ".join(str(item) for item in values)
    limits = field.get("range") or {}
    parts = [f"{key}={value}" for key, value in limits.items()]
    return "  ".join(parts)


def _field_item(ui: Ui, field: dict, values: dict[str, Any]) -> Item:
    path = field["path"]
    current = values.get(path)
    leaf = path.rsplit(".", 1)[-1]
    rules = _rules(field)
    detail = f"{path}  {json.dumps(current, ensure_ascii=False)}  {field['type']}"
    if rules:
        detail += f"  ({rules})"
    if field.get("default") is not None:
        detail += f"  default={json.dumps(field['default'], ensure_ascii=False)}"
    return Item(
        leaf,
        detail=detail,
        action=lambda: edit_field_by_key(ui, path),
    )


def settings_menu(ui: Ui) -> None:
    data = _state(ui)
    if data is None:
        return
    document, fields = data
    values = flatten(document["config"])
    sections: dict[str, list[dict]] = {}
    for field in fields:
        sections.setdefault(field["path"].split(".", 1)[0], []).append(field)
    items = [
        Item(
            "Show current settings",
            detail="effective values and sources",
            action=action(ui, "config", "show"),
        ),
        Item(
            "Show the schema",
            detail="every field, type, and range",
            action=action(ui, "config", "schema"),
        ),
    ]
    for name in sorted(sections):
        group = sections[name]
        items.append(
            Item(
                name,
                detail=f"{len(group)} settings",
                children=[_field_item(ui, field, values) for field in group],
            )
        )
    items.append(Item("Quit", action=quit_menu))
    run(ui, "Settings", items)


def edit_field_by_key(ui: Ui, key: str) -> bool:
    data = _state(ui)
    if data is None:
        return False
    document, fields = data
    values = flatten(document["config"])
    field = next((item for item in fields if item["path"] == key), None)
    if field is None:
        print(ui.paint(f"unknown field: {key}", "bad"))
        return False
    edit_field(ui, field, values.get(key))
    return True


def edit_field(ui: Ui, field: dict, current: Any) -> None:
    path = field["path"]
    choices = field.get("values") or []
    kind = field["type"]
    if choices:
        value = _pick(ui, path, choices, current)
    elif kind == "boolean":
        value = prompts.confirm(path, ui=ui, default=bool(current))
    elif kind in NUMBERS:
        value = _number(ui, path, current, kind)
    else:
        text = prompts.ask(
            path,
            ui=ui,
            default="" if current is None else str(current),
            required=False,
        )
        value = text
    if value is None or value == current:
        print(ui.dim(f"{path} is unchanged"))
        return
    run_args(ui, "config", "set", path, json.dumps(value, ensure_ascii=False))


def _pick(ui: Ui, path: str, choices: list[Any], current: Any) -> Any:
    options = [
        prompts.Option(
            str(choice),
            choice,
            "current" if choice == current else "",
        )
        for choice in choices
    ]
    default = next(
        (index for index, choice in enumerate(choices) if choice == current),
        0,
    )
    return prompts.choose(
        path,
        options,
        ui=ui,
        default=default,
        back=False,
    )


def _number(ui: Ui, path: str, current: Any, kind: str) -> Any:
    while True:
        text = prompts.ask(
            path,
            ui=ui,
            default="" if current is None else str(current),
            required=False,
        )
        if not text:
            return None
        try:
            return int(text) if kind == "integer" else float(text)
        except ValueError:
            print(ui.paint(f"  {path} needs a {kind}", "warn"))
