from __future__ import annotations

import json
from typing import Any

from downcroc.cli.client import CliError, api, get, patch
from downcroc.cli.context import load
from downcroc.cli.output import flatten, json_out, table


def _show(data: dict) -> None:
    print(f"path  {data['path']}")
    if data.get("error"):
        print(f"error {data['error']}")
    flat = flatten(data["config"])
    width = max(len(key) for key in flat)
    for key, value in flat.items():
        print(f"{key:<{width}}  {json.dumps(value, ensure_ascii=False)}")


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
        raise CliError(f"invalid field path: {key}")
    patch: dict[str, Any] = {}
    cursor = patch
    for part in parts[:-1]:
        nested: dict[str, Any] = {}
        cursor[part] = nested
        cursor = nested
    cursor[parts[-1]] = value
    return patch


def run(args: object) -> int:
    paths, _, _ = load()
    with api(paths) as client:
        if args.action == "show":
            data = get(client, "/api/config")
            if args.json:
                json_out(data)
            else:
                _show(data)
            return 0
        if args.action == "schema":
            data = get(client, "/api/config/schema")
            if args.json:
                json_out(data)
            else:
                _schema(data["fields"])
            return 0
        result = patch(
            client,
            "/api/config",
            _patch(args.key, _value(args.value)),
        )
        if args.json:
            json_out(result)
        else:
            changed = result.get("changed") or []
            if not changed:
                print("no changes")
            else:
                print("changed " + ", ".join(changed))
        return 0
