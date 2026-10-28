from __future__ import annotations

from downcroc.cli.client import api, delete, get, get_page, post
from downcroc.cli.context import load
from downcroc.cli.output import json_out, page_footer, record, table
from downcroc.cli.ui import prompts
from downcroc.cli.ui.menu import open_menu
from downcroc.cli.ui.session import Ui, build


def _list(rows: list[dict]) -> None:
    table(
        ["job", "recipient", "code", "attempts", "failed_at", "message"],
        [
            [
                item["job_id"],
                item["recipient"],
                item["code"],
                item["attempts"],
                item["failed_at"],
                item["message"],
            ]
            for item in rows
        ],
    )


def _show(item: dict) -> None:
    record(
        {
            "job": item["job_id"],
            "batch": item["batch_id"],
            "account": item["account_id"],
            "recipient": item["recipient"],
            "code": item["code"],
            "message": item["message"],
            "retryable": item["retryable"],
            "attempts": item["attempts"],
            "failed_at": item["failed_at"],
        }
    )


def _listing(client, args: object, ui: Ui) -> int:
    rows, total = get_page(
        client,
        "/api/failed",
        limit=getattr(args, "limit", None) or 100,
        offset=getattr(args, "offset", 0) or 0,
    )
    if ui.json_mode:
        json_out(rows)
        return 0
    _list(rows)
    page_footer(
        len(rows),
        total,
        limit=getattr(args, "limit", None) or 100,
        offset=getattr(args, "offset", 0) or 0,
    )
    return 0


def _retry_all(client, args: object, ui: Ui) -> int:
    rows, total = get_page(client, "/api/failed", limit=500, offset=0)
    count = total if total is not None else len(rows)
    if count == 0:
        if ui.json_mode:
            json_out({"retried": 0})
        else:
            print("no failures to retry")
        return 0
    accounts = sorted({item["account_id"] for item in rows})
    retryable = sum(1 for item in rows if item["retryable"])
    if not ui.json_mode:
        print(f"{count} failures on {len(accounts)} accounts")
        for account in accounts:
            print(f"  {account}")
        print(f"  {retryable} of the shown failures are retryable")
    prompts.confirm(
        f"retry {count} failures?",
        ui=ui,
        yes_flag=bool(getattr(args, "yes", False)),
    )
    result = post(client, "/api/failed/retry")
    if ui.json_mode:
        json_out(result)
    else:
        print(f"retried {result['retried']} failures")
    return 0


def _forget(client, args: object, ui: Ui) -> int:
    prompts.confirm(
        f"forget failure {args.job_id}?",
        ui=ui,
        yes_flag=bool(getattr(args, "yes", False)),
    )
    result = delete(client, f"/api/failures/{args.job_id}", confirm="true")
    if ui.json_mode:
        json_out(result)
    else:
        print(f"forgot {result['job_id']}")
    return 0


def _purge(client, args: object, ui: Ui) -> int:
    dry_run = bool(args.dry_run)
    if not dry_run:
        prompts.confirm(
            "purge failures?",
            ui=ui,
            yes_flag=bool(getattr(args, "yes", False)),
        )
    result = post(
        client,
        "/api/failures/purge",
        {
            "states": args.states,
            "older_than_days": args.older_than,
            "dry_run": dry_run,
            "confirm": not dry_run,
        },
    )
    if ui.json_mode:
        json_out(result)
    elif result.get("dry_run"):
        print(f"would forget {result['failures']} failures")
    else:
        print(f"forgot {result['failures']} failures")
    return 0


def run(args: object) -> int:
    ui = build(args)
    paths, _, _ = load()
    action = getattr(args, "action", None)
    if action is None and open_menu(ui, "failed_menu"):
        return 0
    with api(paths) as client:
        if action in {None, "list"}:
            return _listing(client, args, ui)
        if action == "retry-all":
            return _retry_all(client, args, ui)
        if action == "forget":
            return _forget(client, args, ui)
        if action == "purge":
            return _purge(client, args, ui)
        if action == "retry":
            job = post(client, f"/api/failed/{args.job_id}/retry")
            if ui.json_mode:
                json_out(job)
            else:
                print(f"retried {job['id']} ({job['state']})")
            return 0
        item = get(client, f"/api/failed/{args.job_id}")
        if ui.json_mode:
            json_out(item)
        else:
            _show(item)
        return 0
