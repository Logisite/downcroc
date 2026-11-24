from __future__ import annotations

from typing import Any

SAFE_FIELDS = (
    "event",
    "id",
    "account",
    "account_id",
    "message",
    "message_id",
    "job",
    "job_id",
    "batch",
    "batch_id",
    "thread",
    "thread_id",
    "reply_state",
    "subject",
    "from",
    "transport",
    "state",
    "created_at",
    "sent_at",
    "received_at",
    "reason",
    "used",
    "reserved",
    "remaining",
    "limit",
    "day",
)


def sanitize(payload: dict[str, Any]) -> dict[str, Any]:
    clean = {key: payload[key] for key in SAFE_FIELDS if key in payload}
    clean["event"] = str(payload.get("event", ""))
    return clean


def call_event(
    extension: str, capability: str, outcome: str, duration_ms: int
) -> dict[str, Any]:
    return {
        "extension": extension,
        "capability": capability,
        "outcome": outcome,
        "duration_ms": duration_ms,
    }
