from __future__ import annotations

from pathlib import Path

from downcroc.cli import inputs, schema
from downcroc.cli import paths as path_tools
from downcroc.cli.client import api, delete, get, get_page, post
from downcroc.cli.context import load
from downcroc.cli.errors import CliError
from downcroc.cli.output import json_out, page_footer, record, table
from downcroc.cli.ui import card, prompts
from downcroc.cli.ui.frame import columns
from downcroc.cli.ui.menu import open_menu
from downcroc.cli.ui.session import Ui, build

COUNT_KEYS = [
    "awaiting_approval",
    "queued",
    "sending",
    "sent",
    "sent_unconfirmed",
    "retry_wait",
    "failed",
    "cancelled",
    "inbound",
    "replies",
    "late_replies",
    "bounces",
    "suppressed",
    "invalid",
]


def _counts(counts: dict) -> dict:
    ordered = {key: counts[key] for key in COUNT_KEYS if key in counts}
    for key in sorted(counts):
        ordered.setdefault(key, counts[key])
    return ordered


def _list(rows: list[dict], ui: Ui) -> None:
    table(
        ["id", "name", "kind", "state", "approval", "sent", "replies", "created"],
        [
            [
                item["id"],
                item["name"],
                item["kind"],
                item["state"],
                item["approval"],
                item["counts"].get("sent", 0),
                item["counts"].get("replies", 0),
                item["created_at"],
            ]
            for item in rows
        ],
    )
    if not rows:
        print("no batches match")
        if not ui.quiet:
            print("next: downcroc batch validate campaign.json")
        return
    waiting = [item for item in rows if item["state"] == "awaiting_approval"]
    if waiting and not ui.quiet:
        print()
        print(f"next: downcroc review ({len(waiting)} waiting)")


def _recipients(rows: list[dict], all_rows: bool) -> None:
    shown = rows if all_rows else rows[:20]
    if shown:
        table(
            ["job", "recipient", "state", "attempts", "sent"],
            [
                [
                    item["id"],
                    item["recipient"],
                    item["state"],
                    item["attempts"],
                    item["sent_at"],
                ]
                for item in shown
            ],
        )
    if not all_rows and len(rows) > len(shown):
        print(f"{len(rows) - len(shown)} more recipients, use --all to show them")


def _routing(batch: dict) -> str:
    routing = batch.get("routing") or {}
    mode = routing.get("mode", "auto")
    if mode == "fixed":
        return f"fixed, {routing.get('account') or batch.get('account_id')}"
    counts = routing.get("counts") or {}
    if counts:
        joined = ", ".join(f"{name} {count}" for name, count in counts.items())
        return f"auto, {joined}"
    return "auto"


def _show(batch: dict, all_rows: bool) -> None:
    record(
        {
            "id": batch["id"],
            "name": batch["name"],
            "kind": batch["kind"],
            "state": batch["state"],
            "approval": batch["approval"],
            "routing": _routing(batch),
            "source": batch["source_ref"],
            "template": batch["template_ref"],
            "created_at": batch["created_at"],
            "approved_at": batch["approved_at"],
        }
    )
    record(_counts(batch["counts"]))
    options = batch.get("options") or {}
    if options:
        record(
            {
                "suppress_replies": options.get("suppress_replies"),
                "reply_window_days": options.get("reply_window_days"),
                "not_before": options.get("not_before"),
                "stop_on": ", ".join(options.get("stop_on") or []),
            }
        )
    for warning in batch.get("warnings") or []:
        print(f"warning: {warning}")
    for field in batch.get("ignored") or []:
        print(f"ignored: {field}")
    _recipients(batch.get("recipients") or [], all_rows)


def show_preview(
    preview: dict,
    ui: Ui,
    *,
    key: str | None = None,
    table_view: bool = False,
) -> None:
    messages = preview["messages"]
    if not table_view:
        _cards(preview, messages[:1] if key is not None else messages, ui, key)
        return
    record(
        {
            "campaign": f"{preview['campaign_name']} ({preview['campaign_key']})",
            "kind": preview["source_kind"],
            "messages": (f"{preview['total']:,} total, showing {preview['sampled']}"),
            "approval": _approval(preview),
            "routing": _preview_routing(preview),
            "followups": _followups(preview),
            "attachments": _attachments(preview),
        }
    )
    if preview.get("duplicates"):
        record({"duplicates": f"{preview['duplicates']} skipped"})
    table(
        ["recipient", "subject", "account"],
        [
            [item["email"], item["subject"], item["account_id"]]
            for item in preview["messages"]
        ],
    )
    for field in preview.get("ignored") or []:
        print(f"ignored: {field}")
    for warning in preview.get("warnings") or []:
        print(f"warning: {warning}")
    if not ui.quiet and preview.get("sampled", 0) < preview.get("total", 0):
        print()
        print(f"next: downcroc batch preview {preview.get('path', 'FILE')} --all")


def _cards(preview: dict, messages: list[dict], ui: Ui, key: str | None) -> None:
    width = max(1, columns(ui) - 1)
    for index, message in enumerate(messages):
        if index:
            print()
        for line in card.message_card(ui, message, width):
            print(line)
    if (
        key is None
        and not ui.quiet
        and preview.get("sampled", 0) < preview.get("total", 0)
    ):
        print()
        print(ui.dim(f"{preview['sampled']} of {preview['total']} shown, pass --all"))


def _approval(preview: dict) -> str:
    if preview["valid"] != preview["total"]:
        return f"{preview['total'] - preview['valid']} invalid, nothing will submit"
    return f"{preview['valid']:,} valid"


def _preview_routing(preview: dict) -> str:
    routing = preview.get("routing") or {}
    mode = routing.get("mode", "auto")
    if mode == "fixed":
        account = routing.get("account_id") or routing.get("account") or "-"
        return f"fixed, {account}, {preview['total']:,} messages"
    counts = routing.get("counts") or {}
    if not counts:
        return "auto, no account"
    joined = ", ".join(f"{name} {count:,}" for name, count in counts.items())
    return f"auto, {joined}"


def _followups(preview: dict) -> str:
    steps = preview.get("followups") or []
    if not steps:
        return "none"
    return ", ".join(
        f"{step['key']} after {step['after_days']}d when {step['when']}"
        for step in steps
    )


def _attachments(preview: dict) -> str:
    value = preview.get("attachments") or {}
    if not value.get("count"):
        return "none"
    return f"{value['count']} files, {value['bytes']:,} bytes"


def show_validation(body: dict) -> None:
    if body["ok"]:
        record(
            {
                "file": body["path"],
                "kind": body["kind"],
                "campaign": f"{body['campaign']['name']} ({body['campaign']['key']})",
                "messages": f"{body['valid']:,} valid",
                "routing": (
                    f"{body['routing']['mode']}"
                    + (
                        f", {body['routing']['account']}"
                        if body["routing"]["account"]
                        else ""
                    )
                ),
                "followups": len(body.get("followups") or []),
                "duplicates": body.get("duplicates", 0),
            }
        )
        for field in body.get("ignored") or []:
            print(f"ignored: {field}")
        return
    print(f"invalid {body['path']}")
    for issue in body.get("issues") or []:
        where = issue.get("field") or "source"
        if issue.get("row") is not None:
            where = f"row {issue['row']}, {where}"
        if issue.get("key"):
            where = f"{issue['key']}, {where}"
        print(f"  {where}: {issue['message']}")
    if body.get("hint"):
        print(f"  hint: {body['hint']}")


def _example(kind: str, write_to: str | None, ui: Ui) -> int:
    if not write_to:
        if ui.json_mode:
            json_out(inputs.EXAMPLES[kind])
            return 0
        for name, content in inputs.EXAMPLES[kind].items():
            print(f"# {name}")
            if isinstance(content, dict):
                import json

                print(json.dumps(content, indent=2))
            else:
                print(content.rstrip())
            print()
        return 0
    directory = path_tools.expand(write_to)
    directory.mkdir(parents=True, exist_ok=True)
    written = inputs.write_example(kind, directory)
    if ui.json_mode:
        json_out([str(path) for path in written])
    else:
        for path in written:
            print(str(path))
        print(f"wrote {len(written)} files to {directory}")
    return 0


def _schema(ui: Ui) -> int:
    if ui.json_mode:
        json_out(schema.CONTRACT)
        return 0
    print(schema_text())
    return 0


def schema_text() -> str:
    lines = [
        f"{schema.SCHEMA}",
        "",
        "detection",
        f"  json   {schema.CONTRACT['detection']['json']}",
        f"  csv    {schema.CONTRACT['detection']['csv']}",
        "",
        "top level: " + ", ".join(schema.CONTRACT["top_level"]),
        "",
        "campaign.routing",
        "  mode      auto or fixed",
        "  account   required when mode is fixed",
        "  include   list of account ids or addresses",
        "  exclude   list of account ids or addresses",
        "",
        "campaign.options",
        "  approval            review or auto",
        "  suppress_replies    boolean, default true",
        "  reply_window_days   0-3650, default 60",
        "  not_before          ISO 8601 timestamp",
        "  stop_on             reply, bounce",
        "  allow_duplicates    boolean, default false",
        "",
        "messages",
        "  key, to{email,name}, subject, text, html, reply_to, attachments, followups",
        "  a per-message account field is rejected; use campaign.routing.account",
        "",
        "followups",
        "  key, after_days 1-365, when no_reply or always, subject, text, html,",
        "  require_approval",
        "",
        "csv needs a template under the config templates directory",
        "next: downcroc batch example --kind json",
    ]
    return "\n".join(lines)


def source_body(args: object) -> dict:
    return {
        "path": str(path_tools.resolve_input(args.path)),
        "template": getattr(args, "template", None),
        "account": getattr(args, "account", None),
    }


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
        return _schema(ui)
    if action == "example":
        return _example(args.kind, args.write, ui)
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
        _show(batch, bool(args.all))
    return 0


def _validate(args: object, ui: Ui) -> int:
    paths, settings, _ = load()
    source = path_tools.resolve_input(args.path)
    body = inputs.validate(source, getattr(args, "template", None), settings, paths)
    if ui.json_mode:
        json_out(body)
    else:
        show_validation(body)
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
        _list(rows, ui)
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
        show_preview(
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
            show_preview(preview, ui, key=key)
            print()
            print("dry run, nothing was written")
        return 0
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


def _cancel(client, args: object, ui: Ui) -> int:
    batch = get(client, f"/api/batches/{args.batch_id}")
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
