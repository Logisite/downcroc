from __future__ import annotations

from downcroc.cli.client import api, get, post
from downcroc.cli.context import load
from downcroc.cli.logs_addresses import AddressBook, book_for, resolve_account
from downcroc.cli.output import json_out, record, table
from downcroc.cli.ui import prompts
from downcroc.cli.ui.session import Ui, build

TOTAL_KEYS = ("due", "waiting", "missing", "unresolved", "open", "total")


def _status(data: dict, ui: Ui, book: AddressBook | None) -> None:
    if ui.json_mode:
        json_out(data)
        return
    record(
        {key: data[key] for key in TOTAL_KEYS}
        | {"next_due_at": data.get("next_due_at")}
    )
    rows = data.get("accounts") or []
    if rows:
        table(
            ["account", "address", "state", *TOTAL_KEYS, "blocked"],
            [
                [
                    resolve_account(book, row["account_id"]),
                    row.get("address") or "-",
                    row["status"],
                    *[row[key] for key in TOTAL_KEYS],
                    row.get("blocked_reason") or "-",
                ]
                for row in rows
            ],
        )
    for account_id in data.get("unknown_accounts") or []:
        print(
            f"note: holes reference unknown account {resolve_account(book, account_id)}"
        )


def _detail(data: dict, ui: Ui, book: AddressBook | None) -> None:
    if ui.json_mode:
        json_out(data)
        return
    record(
        {
            "attempt": data["attempt_id"],
            "job": data["job_id"],
            "account": resolve_account(book, data["account_id"]),
            "address": data.get("address") or "-",
            "state": data.get("account_status") or "unknown",
            "outcome": data["outcome"],
            "message_id": data.get("message_id") or "-",
            "thread": data.get("provider_thread_id") or "-",
            "status": data.get("thread_status") or "open",
            "checks": data["check_count"],
            "last_result": data.get("last_result") or "-",
            "last_scope": data.get("last_scope") or "-",
            "first_miss_at": data.get("first_miss_at") or "-",
            "last_checked_at": data.get("last_checked_at") or "-",
            "next_check_at": data.get("next_check_at") or "-",
            "blocked": data.get("blocked_reason") or "-",
            "error": data.get("last_error") or "-",
        }
    )
    if data.get("blocked_reason") == "needs_reauth":
        print("reconnect this account to let backfill check its remaining holes")


def run(args: object) -> int:
    paths, _, _ = load()
    ui = build(args)
    book = book_for(args)
    with api(paths) as client:
        if args.action == "status":
            _status(get(client, "/api/backfill/status"), ui, book)
            return 0
        attempt_id = args.attempt_id
        if args.action == "explain":
            _detail(get(client, f"/api/backfill/holes/{attempt_id}"), ui, book)
            return 0
        prompts.confirm(
            f"recheck hole {attempt_id} on the next backfill pass?",
            ui=ui,
            yes_flag=bool(getattr(args, "yes", False)),
        )
        _detail(post(client, f"/api/backfill/holes/{attempt_id}/retry"), ui, book)
        return 0
