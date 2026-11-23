from __future__ import annotations

import getpass
import json
import shutil
from pathlib import Path
from typing import Any

from downcroc.cli.client import api, get, post
from downcroc.cli.context import load
from downcroc.cli.output import json_out, table
from downcroc.cli.ui.session import build
from downcroc.extensions import packaging
from downcroc.extensions.errors import ManifestError


def run(args: object) -> int:
    ui = build(args)
    action = getattr(args, "action", None) or "list"
    paths, _, _ = load()
    if action == "build":
        return _build(args)
    with api(paths, timeout=getattr(args, "timeout", None)) as client:
        if action == "list":
            return _list(client, ui.json_mode)
        if action == "show":
            return _show(client, str(args.extension), ui.json_mode)
        if action == "add":
            return _add(paths, str(args.path), client)
        if action == "verify":
            return _verify(client, str(args.extension), ui.json_mode)
        if action == "approval":
            return _show_approval(client, str(args.extension), ui.json_mode)
        if action == "approve":
            return _approve(client, args)
        if action == "revoke":
            return _revoke(client, str(args.extension))
        if action == "enable":
            post(client, f"/api/extensions/{args.extension}/enable")
            return 0
        if action == "disable":
            post(client, f"/api/extensions/{args.extension}/disable")
            return 0
        if action == "reload":
            post(client, "/api/extensions/reload")
            return 0
        if action == "capabilities":
            return _capabilities(client, ui.json_mode)
        if action == "test":
            result = post(
                client,
                f"/api/extensions/{args.extension}/test",
                json.loads(str(args.input)),
            )
            json_out(result)
            return 0
        if action == "run":
            extension = getattr(args, "extension_id", None) or args.extension
            command = getattr(args, "extension_command", None) or args.command
            payload = _parse_args(list(getattr(args, "args", []) or []))
            for key, value in vars(args).items():
                if (
                    not key.startswith("_")
                    and key
                    not in {
                        "command",
                        "action",
                        "extension",
                        "extension_id",
                        "extension_command",
                        "timeout",
                        "json",
                        "no_input",
                    }
                    and value is not None
                ):
                    payload[key] = value
            result = post(
                client,
                f"/api/extensions/{extension}/command/{command}",
                payload,
            )
            json_out(result)
            return 0
        if action == "logs":
            return _logs(paths, str(args.extension), ui.json_mode)
    return 1


def _list(client: Any, json_mode: bool) -> int:
    rows = get(client, "/api/extensions")
    if json_mode:
        json_out(rows)
        return 0
    table(
        ["id", "name", "version", "enabled", "running", "events"],
        [
            [
                row.get("id", ""),
                row.get("name", ""),
                row.get("version", ""),
                "yes" if row.get("enabled") else "no",
                "yes" if row.get("running") else "no",
                ", ".join(row.get("events") or []),
            ]
            for row in rows
        ],
    )
    return 0


def _show(client: Any, extension: str, json_mode: bool) -> int:
    rows = get(client, "/api/extensions")
    row = next((item for item in rows if item.get("id") == extension), None)
    if row is None:
        json_out({"error": "extension_not_found", "extension": extension})
        return 1
    json_out(row) if json_mode else table(
        ["field", "value"], [[key, str(value)] for key, value in row.items()]
    )
    return 0


def _add(paths: Any, source: str, client: Any) -> int:
    origin = Path(source)
    if not origin.is_file():
        json_out({"error": "manifest_not_found", "path": source})
        return 1
    if origin.suffix == ".pyz":
        try:
            manifest = packaging.install(origin, paths.config / "extensions")
        except (ManifestError, ValueError, OSError) as error:
            json_out({"error": "extension_artifact_invalid", "detail": str(error)})
            return 1
        post(client, "/api/extensions/reload")
        json_out(
            {
                "ok": True,
                "id": manifest.id,
                "artifact": manifest.artifact,
                "sha256": manifest.artifact_sha256,
            }
        )
        return 0
    target_dir = paths.config / "extensions"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / origin.name
    shutil.copyfile(origin, target)
    json_out({"ok": True, "path": str(target)})
    return 0


def _build(args: object) -> int:
    try:
        target, checksum = packaging.build(
            Path(str(args.directory)),
            Path(str(args.output)) if getattr(args, "output", None) else None,
        )
    except ValueError as error:
        json_out({"error": "extension_artifact_invalid", "detail": str(error)})
        return 1
    json_out({"path": str(target), "sha256": checksum})
    return 0


def _verify(client: Any, extension: str, json_mode: bool) -> int:
    result = get(client, f"/api/extensions/{extension}/verify")
    if json_mode:
        json_out(result)
        return 0
    table(
        ["field", "value"],
        [[key, str(value)] for key, value in result.items()],
    )
    return 0


def _show_approval(client: Any, extension: str, json_mode: bool) -> int:
    result = get(client, f"/api/extensions/{extension}/approval")
    if json_mode:
        json_out(result)
        return 0
    table(["field", "value"], [[key, str(value)] for key, value in result.items()])
    return 0


def _approve(client: Any, args: object) -> int:
    password = getattr(args, "password", None) or getpass.getpass("Vault password: ")
    result = post(
        client,
        f"/api/extensions/{args.extension}/approve",
        {"password": password},
    )
    json_out(result)
    return 0


def _revoke(client: Any, extension: str) -> int:
    post(client, f"/api/extensions/{extension}/revoke")
    json_out({"ok": True, "extension": extension})
    return 0


def _capabilities(client: Any, json_mode: bool) -> int:
    result = get(client, "/api/extensions/capabilities")
    names = result.get("capabilities", [])
    if json_mode:
        json_out(names)
        return 0
    table(["capability"], [[name] for name in names])
    return 0


def _logs(paths: Any, extension: str, json_mode: bool) -> int:
    rows: list[dict[str, Any]] = []
    if paths.log_file.exists():
        for line in paths.log_file.read_text(encoding="utf-8").splitlines():
            if not line.startswith("{"):
                continue
            try:
                item = json.loads(line)
            except ValueError:
                continue
            if str(item.get("event", "")).startswith("extension."):
                rows.append(item)
    filtered = [row for row in rows if row.get("extension") == extension]
    if json_mode:
        json_out(filtered)
        return 0
    table(
        ["time", "event", "capability", "detail"],
        [
            [
                row.get("ts", ""),
                row.get("event", ""),
                row.get("capability", ""),
                str(row.get("detail", "")),
            ]
            for row in filtered
        ],
    )
    return 0


def _parse_args(items: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    index = 0
    while index < len(items):
        item = items[index]
        if item.startswith("--"):
            key = item[2:]
            value: Any = True
            if index + 1 < len(items) and not items[index + 1].startswith("--"):
                index += 1
                value = items[index]
            result[key] = value
        index += 1
    return result
