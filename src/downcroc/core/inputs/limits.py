from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IntakeLimits:
    max_messages: int
    max_body_bytes: int
    max_attachment_bytes: int
