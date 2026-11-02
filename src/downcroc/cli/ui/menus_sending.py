from __future__ import annotations

from downcroc.cli.ui import prompts
from downcroc.cli.ui.data import need_daemon, one, rows
from downcroc.cli.ui.menu import Item, run_args
from downcroc.cli.ui.session import Ui


def sending_badge(ui: Ui) -> str:
    status = one(ui, "/api/status")
    if status is None:
        return "offline"
    return (
        "paused"
        if (status.get("sending") or {}).get("state") == "paused"
        else "running"
    )


def sending_detail(ui: Ui) -> str:
    status = one(ui, "/api/status")
    if status is None:
        return "daemon not reachable"
    sending = status.get("sending") or {}
    if sending.get("state") != "paused":
        return "sending is running"
    detail = f"paused since {sending.get('since') or '-'}"
    if sending.get("until"):
        detail += f", until {sending['until']}"
    if sending.get("reason"):
        detail += f" ({sending['reason']})"
    return detail


def pause_service(ui: Ui) -> None:
    choice = prompts.choose(
        "Pause sending",
        [
            prompts.Option("15 minutes", "15m", "short brake"),
            prompts.Option("1 hour", "1h", "longer brake"),
            prompts.Option("Until I resume", "", "no deadline"),
        ],
        ui=ui,
        back=False,
    )
    if choice is None:
        return
    reason = prompts.ask(
        "Reason",
        ui=ui,
        required=False,
        field="--reason",
    )
    argv = ["service", "pause"]
    if choice:
        argv.extend(["--for", str(choice)])
    if reason:
        argv.extend(["--reason", reason])
    run_args(ui, *argv)


def pause_account(ui: Ui, account_id: str, address: str) -> None:
    if not prompts.confirm(f"Pause sending for {address}?", ui=ui):
        return
    reason = prompts.ask("Reason", ui=ui, required=False, field="--reason")
    argv = ["account", "pause", account_id]
    if reason:
        argv.extend(["--reason", reason])
    run_args(ui, *argv)


def pause_items(ui: Ui) -> list[Item]:
    found = rows(ui, "/api/accounts")
    if found is None:
        return need_daemon(ui)
    return [
        Item(
            row["address"],
            detail=f"{row['status']}  {row['id']}",
            badge="paused" if row.get("paused_at") else "",
            action=lambda row=row: pause_account(ui, row["id"], row["address"]),
        )
        for row in found
    ]
