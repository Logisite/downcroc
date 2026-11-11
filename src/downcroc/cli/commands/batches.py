from __future__ import annotations

from pathlib import Path

from downcroc.cli import inputs
from downcroc.cli import paths as path_tools
from downcroc.cli.client import api, delete, get, get_page, post
from downcroc.cli.commands import batch_view, when
from downcroc.cli.context import load
from downcroc.cli.errors import CliError
from downcroc.cli.output import json_out, page_footer, record, table
from downcroc.cli.ui import prompts
from downcroc.cli.ui.menu import open_menu
from downcroc.cli.ui.session import Ui, build


def source_body(args: object) -> dict:
    return {
        "path": str(path_tools.resolve_input(args.path)),
        "template": getattr(args, "template", None),
        "account": getattr(args, "account", None),
    }


def _cancelled() -> None:
    raise CliError("cancelled", code="cancelled")


def _confirm_batch(ui: Ui, args: object, batch: dict, question: str) -> None:
    if getattr(args, "yes", False):
        return
    if not prompts.confirm(question, ui=ui, default=False):
        raise CliError("cancelled", code="cancelled")
    del batch


def run(args: object) -> int:
    ui = build(args)
    action = getattr(args, "action", None)
    if action is None:
        if open_menu(ui, "batch_menu"):
            return 0
        action = "list"
    if action == "schema":
        return batch_view.show_schema(ui)
    if action == "example":
        return batch_view.example(args.kind, args.write, ui)
    if action == "validate":
        return _validate(args, ui)
    paths, _, _ = load()
    with api(paths, timeout=getattr(args, "timeout", None)) as client:
        if action == "list":
            return _listing(client, args, ui)
        if action == "preview":
            return _preview_command(client, args, ui)
        if action == "submit":
            return _submit(client, args, ui)
        if action == "approve":
            return _approve(client, args, ui)
        if action in {"pause", "resume"}:
            return _hold(client, args, ui, action)
        if action == "cancel":
            return _cancel(client, args, ui)
        if action == "reassign":
            return _reassign(client, args, ui)
        if action == "delete":
            return _delete(client, args, ui)
        if action == "followup":
            return _followup(client, args, ui)
        if action == "suppression":
            return _suppression(client, args, ui)
        batch = get(client, f"/api/batches/{args.batch_id}")
    if ui.json_mode:
        json_out(batch)
    else:
        batch_view.show_batch(batch, bool(args.all), ui)
    return 0


def _validate(args: object, ui: Ui) -> int:
    paths, settings, _ = load()
    source = path_tools.resolve_input(args.path)
    body = inputs.validate(source, getattr(args, "template", None), settings, paths)
    if body.get("ok"):
        try:
            with api(paths, timeout=getattr(args, "timeout", None)) as client:
                preview = post(
                    client,
                    "/api/batches/preview",
                    {
                        "path": str(source),
                        "template": getattr(args, "template", None),
                        "account": getattr(args, "account", None),
                    },
                )
            body["overlap"] = preview.get("overlap")
        except CliError:
            body["overlap"] = None
    if ui.json_mode:
        json_out(body)
    else:
        batch_view.show_validation(body)
    return 0 if body["ok"] else 1


def _listing(client, args: object, ui: Ui) -> int:
    rows, total = get_page(
        client,
        "/api/batches",
        state=getattr(args, "state", None),
        limit=getattr(args, "limit", None) or 100,
        offset=getattr(args, "offset", 0) or 0,
    )
    if ui.json_mode:
        json_out(rows)
    else:
        batch_view.listing(rows, ui)
        page_footer(
            len(rows),
            total,
            limit=getattr(args, "limit", None) or 100,
            offset=getattr(args, "offset", 0) or 0,
        )
    return 0


def _preview_command(client, args: object, ui: Ui) -> int:
    body = source_body(args)
    preview = post(
        client,
        "/api/batches/preview",
        {
            "path": body["path"],
            "template": body["template"],
            "account": body["account"],
        },
        key=getattr(args, "key", None),
        all=getattr(args, "all", False),
    )
    if ui.json_mode:
        json_out(preview)
    else:
        batch_view.show_preview(
            preview,
            ui,
            key=getattr(args, "key", None),
            table_view=getattr(args, "table", False),
        )
    return 0


def _submit(client, args: object, ui: Ui) -> int:
    body = source_body(args)
    key = getattr(args, "key", None)
    if args.dry_run:
        preview = post(
            client,
            "/api/batches/preview",
            body,
            key=key,
        )
        if ui.json_mode:
            json_out({"dry_run": True, "preview": preview})
        else:
            batch_view.show_preview(preview, ui, key=key)
            print()
            print("dry run, nothing was written")
        return 0
    preview = post(client, "/api/batches/preview", body)
    overlap = preview.get("overlap") or {}
    if overlap and not getattr(args, "allow_overlap", False):
        count = overlap.get("count", 0)
        batches = ", ".join(overlap.get("batches") or [])
        prompts.confirm(
            f"{count} recipients already appear in {batches}. Submit anyway?",
            ui=ui,
            default=False,
            yes_flag=False,
        ) or _cancelled()
    batch = post(client, "/api/batches", {**body, "key": key})
    reused = bool(batch.get("reused"))
    if args.approve != "none" and batch["state"] == "awaiting_approval":
        approved = post(
            client,
            f"/api/batches/{batch['id']}/approve",
            {"mode": args.approve},
        )
        approved["reused"] = reused
        batch = approved
    if ui.json_mode:
        json_out(batch)
    else:
        record(
            {
                "reused" if reused else "submitted": (
                    f"{batch['id']} ({batch['name']})"
                ),
                "state": batch["state"],
                "approval": batch["approval"],
            }
        )
        when.show_capacity(batch.get("capacity"), ui)
        if not ui.quiet:
            if batch["state"] == "awaiting_approval":
                print(f"next: downcroc batch approve {batch['id']} --mode all")
            else:
                print(f"next: downcroc batch show {batch['id']}")
    return 0


def _approve(client, args: object, ui: Ui) -> int:
    batch = get(client, f"/api/batches/{args.batch_id}")
    _confirm_batch(
        ui,
        args,
        batch,
        f"approve {batch['name']} with mode {args.mode}?",
    )
    updated = post(
        client,
        f"/api/batches/{args.batch_id}/approve",
        {"mode": args.mode},
    )
    if ui.json_mode:
        json_out(updated)
    else:
        record(
            {"approved": f"{updated['id']} ({args.mode})", "state": updated["state"]}
        )
    return 0


def _hold(client, args: object, ui: Ui, action: str) -> int:
    body = {"reason": getattr(args, "reason", None)}
    if getattr(args, "all", False):
        result = post(client, f"/api/batches/{action}", {**body, "all": True})
        if ui.json_mode:
            json_out(result)
            return 0
        record({"batches": result["count"], "action": action})
        return 0
    if not getattr(args, "batch_id", None):
        raise CliError(
            f"batch {action} needs an id or --all", code="usage", exit_code=2
        )
    result = post(client, f"/api/batches/{args.batch_id}/{action}", body)
    if ui.json_mode:
        json_out(result)
        return 0
    record({"batch": args.batch_id, "action": action, "changed": result["changed"]})
    return 0


def _cancel(client, args: object, ui: Ui) -> int:
    batch = get(client, f"/api/batches/{args.batch_id}")
    if batch["state"] in {"cancelled", "done"}:
        print(ui.result(False, f"already {batch['state']}", batch["id"]))
        return 1
    _confirm_batch(ui, args, batch, f"cancel {batch['name']}?")
    updated = post(client, f"/api/batches/{args.batch_id}/cancel")
    if ui.json_mode:
        json_out(updated)
    else:
        record({"cancelled": updated["id"], "state": updated["state"]})
        print("mail already in flight cannot be recalled")
    return 0


def _reassign(client, args: object, ui: Ui) -> int:
    dry_run = bool(args.dry_run)
    if not dry_run:
        prompts.confirm(
            f"move batch {args.batch_id} to {args.to_account_id}?",
            ui=ui,
            yes_flag=bool(getattr(args, "yes", False)),
        )
    result = post(
        client,
        f"/api/batches/{args.batch_id}/reassign",
        {
            "to_account_id": args.to_account_id,
            "states": args.states,
            "include_failed": args.include_failed,
            "dry_run": dry_run,
            "confirm": not dry_run,
        },
    )
    if ui.json_mode:
        json_out(result)
        return 0
    verb = "would move" if result["dry_run"] else "moved"
    print(f"{verb} {result['jobs']} jobs")
    for item in result["skipped"]:
        print(f"  skipped {item['id']}: {item['reason']}")
    return 0


def _delete(client, args: object, ui: Ui) -> int:
    dry_run = bool(args.dry_run)
    if not dry_run:
        prompts.confirm(
            f"delete batch {args.batch_id}?",
            ui=ui,
            yes_flag=bool(getattr(args, "yes", False)),
        )
    result = delete(
        client,
        f"/api/batches/{args.batch_id}",
        confirm="true" if not dry_run else None,
        dry_run="true" if dry_run else None,
    )
    if ui.json_mode:
        json_out(result)
    elif result.get("dry_run"):
        print(f"would delete {result['batch_id']} and {result['jobs']} jobs")
    else:
        print(f"deleted {result['batch_id']} and {result['jobs']} jobs")
    return 0


def _followup(client, args: object, ui: Ui) -> int:
    source = path_tools.resolve_input(args.path)
    batch = post(
        client,
        f"/api/batches/{args.batch_id}/followups",
        {
            "path": str(source),
            "template": args.template,
            "account": args.account,
            "step": args.step,
            "require_approval": bool(args.require_approval),
        },
    )
    if ui.json_mode:
        json_out(batch)
    else:
        record({"follow-up": f"{batch['id']} ({batch['state']})"})
    return 0


def _suppression(client, args: object, ui: Ui) -> int:
    rows = get(client, f"/api/batches/{args.batch_id}/suppression-preview")
    if ui.json_mode:
        json_out(rows)
        return 0
    if not rows:
        print("no suppressed recipients")
        return 0
    table(
        ["address", "account", "reason"],
        [[item["address"], item["account_id"], item["reason"]] for item in rows],
    )
    return 0


def file_kind(path: Path) -> str:
    try:
        first = path.read_bytes().lstrip()[:1]
    except OSError:
        return "unknown"
    return "json" if first in {b"{", b"["} else "csv"
