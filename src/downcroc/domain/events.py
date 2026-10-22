from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Event:
    seq: int
    type: str
    ts: str
    data: dict[str, Any]
