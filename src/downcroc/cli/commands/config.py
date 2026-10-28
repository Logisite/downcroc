from __future__ import annotations

import json
from typing import Any

from downcroc.cli.client import api, get, patch
from downcroc.cli.context import load
from downcroc.cli.errors import CliError
from downcroc.cli.output import flatten, json_out, table
from downcroc.cli.ui import prompts
from downcroc.cli.ui.menu import open_menu
from downcroc.cli.ui.session import build


def _sources(document: dict[str, Any] | None) -> dict[str, str]:
    if document is None:
        return {}
    return {key: "file" for key in flatten(document)}


def _show(data: dict) -> None:
    print(f"path  {data['path']}")
    if data.get("error"):
        print(f"error {data['error']}")
    flat = flatten(data["config"])
    sources = _sources(data.get("document"))
    table(
        ["field", "value", "source"],
        [
            [key, json.dumps(value, ensure_ascii=False), sources.get(key, "default")]
            for key, value in flat.items()
        ],
    )


def _schema(fields: list[dict]) -> None:
    table(
        ["field", "type", "default", "range", "description"],
        [
            [
                field["path"],
                field["type"],
                field["default"],
                _range(field),
                field["description"],
            ]
            for field in fields
        ],
    )


def _range(field: dict) -> str:
    values = field.get("values")
    if values:
        return ", ".join(str(value) for value in values)
    limits = field.get("range") or {}
    return ", ".join(f"{key}={value}" for key, value in limits.items())


def _value(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _patch(key: str, value: Any) -> dict[str, Any]:
    parts = key.split(".")
    if any(not part for part in parts):
        raise CliError(f"invalid field path: {key}", code="config_rejected")
    patch: dict[str, Any] = {}
    cursor = patch
    for part in parts[:-1]:
        nested: dict[str, Any] = {}
        cursor[part] = nested
        cursor = nested
    cursor[parts[-1]] = value
    return patch


def _restart_keys(fields: list[dict]) -> set[str]:
    return {field["path"] for field in fields if field.get("restart_required")}


def _set(client, args: object, ui) -> int:
    current = get(client, "/api/config")
    schema = get(client, "/api/config/schema")
    before = flatten(current["config"]).get(args.key)
    text = getattr(args, "value", None)
    if text is None:
        default = json.dumps(before, ensure_ascii=False)
        text = prompts.ask(args.key, ui=ui, default=default, required=False)
        if not text or text == default:
            print(ui.dim(f"{args.key} is unchanged"))
            return 0
    result = patch(client, "/api/config", _patch(args.key, _value(text)))
    after = flatten(result["config"]).get(args.key)
    body = {
        "key": args.key,
        "old": before,
        "new": after,
        "changed": result.get("changed") or [],
        "restart_required": args.key in _restart_keys(schema["fields"]),
    }
    if ui.json_mode:
        json_out(body)
        return 0
    if not body["changed"]:
        value = json.dumps(after, ensure_ascii=False)
        print(ui.result(True, "unchanged", f"{args.key} is {value}"))
        return 0
    old = json.dumps(before, ensure_ascii=False)
    new = json.dumps(after, ensure_ascii=False)
    print(ui.result(True, "set", f"{args.key}: {old} -> {new}"))
    if body["restart_required"]:
        print("restart the daemon to apply this change: downcroc service restart")
    return 0


def run(args: object) -> int:
    paths, _, _ = load()
    ui = build(args)
    action = getattr(args, "action", None)
    if action is None:
        if open_menu(ui, "settings_menu"):
            return 0
        action = "show"
    if action == "set" and not getattr(args, "key", None):
        if open_menu(ui, "settings_menu"):
            return 0
        raise CliError("config set needs a field", code="usage", exit_code=2)
    with api(paths) as client:
        if action == "show":
            data = get(client, "/api/config")
            if ui.json_mode:
                json_out(data)
            else:
                _show(data)
            return 0
        if action == "schema":
            data = get(client, "/api/config/schema")
            if ui.json_mode:
                json_out(data)
            else:
                _schema(data["fields"])
            return 0
        return _set(client, args, ui)
