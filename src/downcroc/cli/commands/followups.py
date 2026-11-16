from __future__ import annotations

from downcroc.cli import reltime
from downcroc.cli.client import api, get
from downcroc.cli.context import load
from downcroc.cli.output import json_out, table
from downcroc.cli.ui.session import build


def run(args: object) -> int:
    ui = build(args)
    action = getattr(args, "action", None) or "due"
    if action != "due":
        action = "due"
    paths, _, _ = load()
    with api(paths, timeout=getattr(args, "timeout", None)) as client:
        payload = get(
            client,
            "/api/followups/outlook",
            due=getattr(args, "due", "today") or "today",
        )
    items = payload.get("items") or []
    if ui.json_mode:
        json_out(payload)
        return 0
    table(
        ["batch", "name", "step", "rule", "due", "counts"],
        [
            [
                item["batch_id"],
                item["batch_name"],
                item["step"],
                f"{item['when']} +{item['after_days']}d",
                _due_cell(item),
                _counts_cell(item),
            ]
            for item in items
        ],
    )
    if not items:
        print("no follow-ups due")
    return 0


def _due_cell(item: dict) -> str:
    state = item.get("state")
    if state in {"pending", "awaiting_approval", "sending"}:
        return "due now"
    due_at = item.get("next_due_at")
    if due_at:
        return reltime.in_time(due_at)
    return "-"


def _counts_cell(item: dict) -> str:
    counts = item.get("counts") or {}
    parts: list[str] = []
    ready = int(counts.get("candidates", 0))
    if item.get("state") == "pending" and ready > 0:
        parts.append(f"{ready} due")
    awaiting = int(counts.get("awaiting", 0))
    if awaiting:
        parts.append(f"{awaiting} awaiting")
    waiting = int(counts.get("not_due", 0)) + int(counts.get("pending", 0))
    if waiting and item.get("state") != "pending":
        parts.append(f"{waiting} waiting")
    elif int(counts.get("not_due", 0)):
        parts.append(f"{int(counts.get('not_due', 0))} waiting")
    replied = int(counts.get("replied", 0))
    if replied:
        parts.append(f"{replied} replied")
    sent = int(counts.get("sent", 0))
    if sent and not parts:
        parts.append(f"{sent} sent")
    return " · ".join(parts) if parts else "-"
