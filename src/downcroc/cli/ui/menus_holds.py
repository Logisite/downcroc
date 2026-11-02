from __future__ import annotations

from downcroc.cli.ui.data import action, need_daemon, rows
from downcroc.cli.ui.menu import Item
from downcroc.cli.ui.session import Ui


def batch_hold_items(ui: Ui, verb: str) -> list[Item]:
    found = rows(ui, "/api/batches")
    if found is None:
        return need_daemon(ui)
    if not found:
        return [Item("No batches yet", detail="submit a campaign first")]
    return [
        Item(
            row["name"],
            detail=f"{row['state']}  {row['id']}",
            badge="paused" if row.get("paused_at") else "",
            action=action(ui, "batch", verb, row["id"]),
        )
        for row in found
    ]


def job_hold_items(ui: Ui, verb: str) -> list[Item]:
    found = rows(ui, "/api/jobs")
    if found is None:
        return need_daemon(ui)
    if not found:
        return [Item("No jobs yet", detail="submit a campaign first")]
    return [
        Item(
            row["recipient"],
            detail=f"{row['state']}  {row['id']}",
            badge="paused" if row.get("paused_at") else "",
            action=action(ui, "job", verb, row["id"]),
        )
        for row in found
    ]
