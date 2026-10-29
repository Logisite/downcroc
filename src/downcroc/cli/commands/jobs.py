from __future__ import annotations

from downcroc.cli import paths as path_tools
from downcroc.cli.client import api, delete, get, get_page, post
from downcroc.cli.commands.job_view import (
    attempts_table,
    job_list,
    job_show,
    sender_label,
)
from downcroc.cli.context import load
from downcroc.cli.errors import CliError
from downcroc.cli.output import json_out, page_footer
from downcroc.cli.ui import prompts
from downcroc.cli.ui.menu import open_menu
from downcroc.cli.ui.session import Ui, build


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
    job_list(rows)
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
    print(f"  sender  {sender_label(job)}")
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
            _reassign_question(args),
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
            "pin": args.pin,
            "unpin": args.unpin,
            "dry_run": dry_run,
            "confirm": not dry_run,
        },
    )
    if ui.json_mode:
        json_out(result)
        return 0
    verb = "would move" if result["dry_run"] else "moved"
    print(f"{verb} {result['jobs']} jobs in {result['batches']} batches")
    if result["pinned"]:
        print(f"  pinned {result['pinned']}")
    if result["unpinned"]:
        print(f"  unpinned {result['unpinned']}, routed at send time")
    for item in result["skipped"]:
        print(f"  skipped {item['id']}: {item['reason']}")
    return 0


def _reassign_question(args: object) -> str:
    if args.unpin:
        return "route these jobs at send time?"
    if args.pin:
        return f"pin these jobs to {args.to_account_id}?"
    return f"move these jobs to {args.to_account_id}?"


def _attempts(client, args: object, ui: Ui) -> int:
    rows = get(client, f"/api/jobs/{args.job_id}/attempts")
    if ui.json_mode:
        json_out(rows)
        return 0
    if not rows:
        print("no send attempts yet")
        return 0
    attempts_table(rows)
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
        if action == "attempts":
            return _attempts(client, args, ui)
        job = get(client, f"/api/jobs/{args.job_id}")
        if ui.json_mode:
            json_out(job)
        else:
            job_show(job)
        return 0
