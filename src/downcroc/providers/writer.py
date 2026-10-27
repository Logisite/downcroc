from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

MODE = 0o600
HEADER = "# written by downcroc; hand edits are kept, comments are not\n"


def read(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    providers = data.get("providers")
    if not isinstance(providers, dict):
        return {}
    return {
        key: dict(values)
        for key, values in providers.items()
        if isinstance(values, dict)
    }


def write(path: Path, providers: dict[str, dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [HEADER]
    for provider_id in sorted(providers):
        lines.append(f"[providers.{provider_id}]")
        for key, value in providers[provider_id].items():
            lines.append(f"{key} = {_value(value)}")
        lines.append("")
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    if os.name != "nt":
        temporary.chmod(MODE)
    temporary.replace(path)


def _value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_value(item) for item in value) + "]"
    if isinstance(value, dict):
        pairs = ", ".join(f"{key} = {_value(item)}" for key, item in value.items())
        return "{ " + pairs + " }"
    return _string(str(value))


def _string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'
