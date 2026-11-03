from __future__ import annotations

from downcroc.cli.client import get
from downcroc.cli.commands import when
from downcroc.cli.errors import CliError
from downcroc.cli.output import json_out, record, table
from downcroc.cli.ui import prompts
from downcroc.cli.ui.session import Ui


def choose_account(client, ui: Ui, verb: str, *, archived: bool = False) -> str:
    params = {"archived": "true"} if archived else {}
    rows = get(client, "/api/accounts", **params)
    if not rows:
        hint = "archive an account first" if archived else "run downcroc account add"
        raise CliError(
            "no archived accounts are available"
            if archived
            else "no accounts are configured",
            code="usage",
            hint=hint,
            exit_code=2,
        )
    chosen = prompts.choose(
        f"Account to {verb}",
        [prompts.Option(row["address"], row["id"], row["status"]) for row in rows],
        ui=ui,
        back=False,
    )
    if chosen is None:
        raise CliError("cancelled", code="cancelled")
    return str(chosen)


def listing(rows: list[dict], ui: Ui, *, archived: bool = False) -> None:
    table(
        [
            "id",
            "address",
            "provider",
            "status",
            "credential",
            "watcher",
            "archived",
            "error",
        ],
        [
            [
                item["id"],
                item["address"],
                item["provider"],
                f"{item['status']} (paused)"
                if item.get("paused_at")
                else item["status"],
                "yes" if item["credential_present"] else "no",
                "on" if item["watcher_enabled"] else "off",
                item.get("archived_at") or "",
                item["last_error"],
            ]
            for item in rows
        ],
    )
    if archived:
        if not ui.quiet:
            print()
            print("next: run downcroc account unarchive ACCOUNT")
        return
    attention = [item for item in rows if item["status"] != "connected"]
    for item in attention:
        print()
        print(
            f"{item['id']} is {item['status']}: run downcroc account connect {item['id']}"
        )
    if not ui.quiet:
        print()
        print("next: downcroc account add --provider gmail --address you@example.com")


def show(account: dict) -> None:
    record(
        {
            "id": account["id"],
            "provider": account["provider"],
            "address": account["address"],
            "label": account["label"],
            "status": account["status"],
            "sending": "paused" if account.get("paused_at") else "running",
            "credential": account["credential_present"],
            "watcher": account["watcher_enabled"],
            "created_at": account["created_at"],
            "last_verified_at": account["last_verified_at"],
            "last_error": account["last_error"],
            "inbound": (f"{account['inbound']['owner']} {account['inbound']['mode']}"),
            "inbound_override": account["inbound"]["override"] or "auto",
        }
    )
    record(
        {
            "last_uid": account["sync"]["last_uid"],
            "uidvalidity": account["sync"]["uidvalidity"],
            "history_id": account["sync"]["history_id"] or "-",
            "last_sync_at": account["sync"]["last_sync_at"],
            "last_sweep_at": account["sync"]["last_sweep_at"] or "-",
            "failures": account["sync"]["consecutive_failures"],
            "allowance": account["quota"]["daily_allowance"],
            "window": (
                f"{account['quota']['window_start']}..{account['quota']['window_end']}"
            ),
            "in_flight": account["quota"]["max_in_flight"],
        }
    )


def added(account: dict, ui: Ui, *, hint: bool = True) -> int:
    if ui.json_mode:
        json_out(account)
        return 0
    record(
        {
            "account": f"{account['id']} {account['address']}",
            "status": account["status"],
        }
    )
    if hint:
        print(f"next: downcroc account connect {account['id']}")
    return 0


def transports(client, account_id: str, ui: Ui) -> None:
    rows = get(client, f"/api/accounts/{account_id}/transports")
    if not rows:
        print()
        print("this mailbox has no send transports")
        if not ui.quiet:
            print(f"next: downcroc account transport add {account_id} --kind gmail_api")
        return
    print()
    print(ui.heading("send transports"))
    table(
        [
            "id",
            "kind",
            "slot",
            "priority",
            "health",
            "lanes",
            "rate",
            "cooldown",
            "last error",
            "last success",
        ],
        [
            [
                item["id"],
                item["kind"],
                item.get("slot") or "-",
                item["priority"],
                item["health"],
                item["max_concurrency"],
                item["rate_per_min"] or "-",
                item["cooldown_until"] or "-",
                item["last_error_code"] or "-",
                item["last_success_at"] or "-",
            ]
            for item in rows
        ],
    )
    for item in rows:
        history = get(
            client,
            f"/api/accounts/{account_id}/transports/{item['id']}/events",
            limit=5,
        )
        if not history:
            continue
        print()
        print(ui.dim(f"timeline {item['id']} ({item['kind']})"))
        table(
            ["when", "event", "reason", "retry"],
            [
                [
                    row["ts"],
                    str(row["type"]).removeprefix("transport."),
                    row.get("reason") or "-",
                    when.duration(row.get("retry_s")),
                ]
                for row in history
            ],
        )


def deletion_view(preview: dict) -> None:
    counts = preview["counts"]
    record(
        {
            "account": preview["account_id"],
            "pinned_jobs": counts.get("pinned_jobs", 0),
            "auto_jobs": counts.get("auto_jobs", 0),
            "batches": counts.get("batches", 0),
            "batches_pinned": counts.get("batches_pinned", 0),
            "messages": counts.get("messages", 0),
            "blockers": ", ".join(preview["blockers"]) or "none",
        }
    )
    if counts.get("auto_jobs"):
        print("  auto jobs keep routing after the delete")
