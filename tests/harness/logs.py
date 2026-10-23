from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.conftest import Stack


def events(stack: Stack) -> dict[str, list[dict]]:
    path = stack.daemon.data_home / "downcroc" / "logs" / "downcroc.jsonl"
    found: dict[str, list[dict]] = {}
    for line in path.read_text().splitlines():
        if not line.startswith("{"):
            continue
        item = json.loads(line)
        found.setdefault(item["event"], []).append(item)
    return found
