from __future__ import annotations

from datetime import UTC, datetime

from downcroc.cli.output import record
from downcroc.cli.ui.session import Ui


def _parsed(value: object) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def duration(seconds: object) -> str:
    if seconds is None:
        return "-"
    try:
        total = max(0, int(float(str(seconds))))
    except TypeError, ValueError:
        return "-"
    if total < 60:
        return f"{total}s"
    minutes = total // 60
    if minutes < 60:
        return f"{minutes}m"
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return f"{hours}h {minutes}m" if minutes else f"{hours}h"
    days, hours = divmod(hours, 24)
    return f"{days}d {hours}h" if hours else f"{days}d"


def finish(value: object) -> str:
    at = _parsed(value)
    if at is None:
        return "-"
    seconds = (at - datetime.now(UTC)).total_seconds()
    if seconds <= 0:
        return "now"
    return f"~{duration(seconds)}"


def window(value: object) -> str:
    if not isinstance(value, dict):
        return "-"
    earliest = finish(value.get("earliest"))
    latest = finish(value.get("latest"))
    if earliest == "-" and latest == "-":
        return "-"
    if earliest == latest:
        return earliest
    return f"{earliest} to {latest}"


def age(value: object) -> str:
    at = _parsed(value)
    if at is None:
        return "-"
    seconds = max(0, int((datetime.now(UTC) - at).total_seconds()))
    return f"{duration(seconds)} ago" if seconds else "now"


def cell(eta: dict | None) -> str:
    """One column: a compact ETA or the reason it has none."""
    if not eta:
        return "-"
    state = str(eta.get("state") or "")
    if state == "awaiting_approval":
        return "awaiting approval"
    if state == "blocked":
        return f"blocked: {eta.get('blocked_reason') or 'unknown'}"
    if state in {"done", "cancelled"}:
        return state
    latest = (eta.get("finish_at") or {}).get("latest")
    if latest:
        return finish(latest)
    return state or "-"


def show_eta(eta: dict | None, ui: Ui) -> None:
    if not eta:
        return
    record(
        {
            "eta_state": eta.get("state"),
            "as_of": eta.get("as_of"),
            "eta_age": age(eta.get("as_of")),
            "basis": eta.get("basis"),
            "remaining": eta.get("remaining"),
            "sendable": eta.get("sendable"),
            "held": eta.get("held"),
            "lanes": eta.get("lanes"),
            "seats": eta.get("seats"),
            "queue": eta.get("queue_position"),
            "sender_hint": eta.get("sender_hint"),
            "transport_hint": eta.get("transport_hint"),
            "finish": window(eta.get("finish_at")),
            "spills_window": eta.get("spills_window"),
            "spills_day": eta.get("spills_day"),
            "blocked_by": eta.get("blocked_by"),
            "blocked_reason": eta.get("blocked_reason"),
        }
    )
    if eta.get("state") == "awaiting_approval":
        print(ui.dim("waiting for approval; no finish estimate yet"))
    _advice(eta.get("advice"), ui)


def show_capacity(capacity: dict | None, ui: Ui) -> None:
    if not capacity:
        return
    span = capacity.get("duration_s") or {}
    record(
        {
            "messages": capacity.get("messages"),
            "as_of": capacity.get("as_of"),
            "eta_age": age(capacity.get("as_of")),
            "basis": capacity.get("basis"),
            "lanes": capacity.get("lanes"),
            "seats": capacity.get("seats"),
            "serial": capacity.get("serial"),
            "estimate": (
                f"~{duration(span.get('min'))} to ~{duration(span.get('max'))}"
            ),
            "finish": window(capacity.get("finish_at")),
            "spills_window": capacity.get("spills_window"),
            "blocked_reason": capacity.get("blocked_reason"),
        }
    )
    _advice(capacity.get("advice"), ui)


def _advice(text: object, ui: Ui) -> None:
    if not text:
        return
    print()
    print(ui.paint(str(text), "warn"))
