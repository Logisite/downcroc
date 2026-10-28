from __future__ import annotations

from downcroc.cli import paths as path_tools
from downcroc.cli.client import api, delete, get, get_page, post
from downcroc.cli.context import load
from downcroc.cli.errors import CliError
from downcroc.cli.output import json_out, page_footer, record, table
from downcroc.cli.ui import prompts
from downcroc.cli.ui.menu import open_menu
from downcroc.cli.ui.session import Ui, build


def _list(rows: list[dict]) -> None:
    table(
        ["id", "recipient", "state", "attempts", "subject", "sent"],
        [
            [
                item["id"],
                item["recipient"],
                item["state"],
                item["attempts"],
                item["subject"],
                item["sent_at"],
            ]
            for item in rows
        ],
    )


def _show(job: dict) -> None:
    error = job.get("last_error") or {}
    record(
        {
            "id": job["id"],
            "batch": job["batch_id"],
            "account": job["account_id"],
            "recipient": job["recipient"],
            "name": job["recipient_name"],
            "subject": job["subject"],
            "state": job["state"],
            "attempts": job["attempts"],
            "message_id": job["message_id"],
            "thread_root": job["thread_root_job_id"],
            "next_attempt_at": job["next_attempt_at"],
            "sent_at": job["sent_at"],
            "error": error.get("code"),
            "error_message": error.get("message"),
        }
    )


def _contents(parser: object) -> tuple[str, str | None]:
    text = getattr(parser, "text", None)
    text_file = getattr(parser, "text_file", None)
    html = getattr(parser, "html", None)
    html_file = getattr(parser, "html_file", None)
    if text_file is not None:
        text = path_tools.read_text(text_file, field="text_file")
    if html_file is not None:
        html = path_tools.read_text(html_file, field="html_file")
    return text or "", html


def _listing(client, args: object, ui: Ui) -> int:
    rows, total = get_page(
        client,
        "/api/jobs",
        batch=getattr(args, "batch", None),
        account=getattr(args, "account", None),
        state=getattr(args, "state", None),
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


def _account(client, account_id: str) -> dict:
    return get(client, f"/api/accounts/{account_id}")


def _preflight(client, account_id: str, force: bool, ui: Ui) -> None:
    account = _account(client, account_id)
    if account["status"] == "connected":
        return
    message = (
        f"{account['address']} is {account['status']}, "
        "so the send will wait until it connects"
    )
    if force:
        if not ui.json_mode:
            print(f"warning: {message}")
        return
    raise CliError(
        message,
        code="account_not_connected",
        fields={"account": account_id, "status": account["status"]},
        hint=f"run `downcroc account connect {account_id}`, or pass --force",
    )


def _confirm_send(job: dict, args: object, ui: Ui) -> None:
    if not ui.interactive:
        prompts.confirm(
            "send this job now?",
            ui=ui,
            yes_flag=bool(getattr(args, "yes", False)),
        )
        return
    print(f"  to      {job['recipient']}")
    print(f"  subject {job['subject']}")
    print(f"  account {job['account_id']}")
    prompts.confirm(
        "send this job now?",
        ui=ui,
        yes_flag=bool(getattr(args, "yes", False)),
    )


def _create(client, args: object, ui: Ui) -> int:
    _preflight(client, args.account_id, bool(args.force), ui)
    text, html = _contents(args)
    job = post(
        client,
        "/api/jobs",
        {
            "account_id": args.account_id,
            "recipient": args.recipient,
            "recipient_name": args.recipient_name,
            "subject": args.subject,
            "text": text,
            "html": html,
            "batch_id": args.batch,
        },
    )
    if args.send:
        _confirm_send(job, args, ui)
        job = post(client, f"/api/jobs/{job['id']}/send")
    if ui.json_mode:
        json_out(job)
    else:
        print(f"created {job['id']} ({job['state']})")
    return 0


def _send(client, args: object, ui: Ui) -> int:
    job = get(client, f"/api/jobs/{args.job_id}")
    _confirm_send(job, args, ui)
    sent = post(client, f"/api/jobs/{args.job_id}/send")
    if ui.json_mode:
        json_out(sent)
    else:
        print(f"{sent['id']} {sent['state']}")
    return 0


def _cancel(client, args: object, ui: Ui) -> int:
    job = post(client, f"/api/jobs/{args.job_id}/cancel")
    if ui.json_mode:
        json_out(job)
    else:
        print(f"{job['id']} {job['state']}")
    return 0


def _delete(client, args: object, ui: Ui) -> int:
    dry_run = bool(args.dry_run)
    if not dry_run:
        prompts.confirm(
            f"delete job {args.job_id}?",
            ui=ui,
            yes_flag=bool(getattr(args, "yes", False)),
        )
    result = delete(
        client,
        f"/api/jobs/{args.job_id}",
        confirm="true" if not dry_run else None,
        force="true" if args.force else None,
        dry_run="true" if dry_run else None,
    )
    if ui.json_mode:
        json_out(result)
    elif result.get("dry_run"):
        print(f"would delete {result['job_id']} ({result['state']})")
    else:
        print(f"deleted {result['job_id']} ({result['state']})")
    return 0


def _reassign(client, args: object, ui: Ui) -> int:
    dry_run = bool(args.dry_run)
    if not dry_run:
        prompts.confirm(
            f"move jobs to {args.to_account_id}?",
            ui=ui,
            yes_flag=bool(getattr(args, "yes", False)),
        )
    result = post(
        client,
        "/api/jobs/reassign",
        {
            "from_account_id": args.from_account_id,
            "to_account_id": args.to_account_id,
            "job_ids": args.job_ids,
            "batch_ids": args.batch_ids,
            "states": args.states,
            "created_since": args.since,
            "created_until": args.until,
            "include_failed": args.include_failed,
            "dry_run": dry_run,
            "confirm": not dry_run,
        },
    )
    if ui.json_mode:
        json_out(result)
        return 0
    verb = "would move" if result["dry_run"] else "moved"
    print(f"{verb} {result['jobs']} jobs in {result['batches']} batches")
    for item in result["skipped"]:
        print(f"  skipped {item['id']}: {item['reason']}")
    return 0


def run(args: object) -> int:
    ui = build(args)
    paths, _, _ = load()
    action = getattr(args, "action", None)
    if action is None and open_menu(ui, "job_menu"):
        return 0
    with api(paths) as client:
        if action in {None, "list"}:
            return _listing(client, args, ui)
        if action == "create":
            return _create(client, args, ui)
        if action == "send":
            return _send(client, args, ui)
        if action == "cancel":
            return _cancel(client, args, ui)
        if action == "delete":
            return _delete(client, args, ui)
        if action == "reassign":
            return _reassign(client, args, ui)
        job = get(client, f"/api/jobs/{args.job_id}")
        if ui.json_mode:
            json_out(job)
        else:
            _show(job)
        return 0
