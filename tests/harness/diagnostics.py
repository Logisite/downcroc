from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.conftest import Stack

LOG_TAIL = 40


def describe(stack: Stack) -> str:
    path = stack.daemon.data_home / "downcroc" / "logs" / "downcroc.jsonl"
    parts = [f"daemon output under {stack.root}:", stack.daemon.tail()]
    if path.exists():
        lines = path.read_text(errors="replace").splitlines()
        parts.append(f"last {LOG_TAIL} log lines:")
        parts.extend(lines[-LOG_TAIL:])
    return "\n".join(parts)
