from __future__ import annotations

import json

from downcroc.cli import inputs, schema
from downcroc.cli import paths as path_tools
from downcroc.cli.commands import when
from downcroc.cli.output import json_out, record, table
from downcroc.cli.ui import card
from downcroc.cli.ui.frame import columns
from downcroc.cli.ui.session import Ui

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


def counts(counts: dict) -> dict:
    ordered = {key: counts[key] for key in COUNT_KEYS if key in counts}
    for key in sorted(counts):
        ordered.setdefault(key, counts[key])
    return ordered


def listing(rows: list[dict], ui: Ui) -> None:
    table(
        [
            "id",
            "name",
            "kind",
            "state",
            "approval",
            "sent",
            "replies",
            "eta",
            "created",
        ],
        [
            [
                item["id"],
                item["name"],
                item["kind"],
                _state(item),
                item["approval"],
                item["counts"].get("sent", 0),
                item["counts"].get("replies", 0),
                when.cell(item.get("eta")),
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


def _state(batch: dict) -> str:
    return f"{batch['state']} (paused)" if batch.get("paused_at") else batch["state"]


def show_batch(batch: dict, all_rows: bool, ui: Ui) -> None:
    record(
        {
            "id": batch["id"],
            "name": batch["name"],
            "kind": batch["kind"],
            "state": _state(batch),
            "approval": batch["approval"],
            "routing": routing(batch),
            "source": batch["source_ref"],
            "template": batch["template_ref"],
            "created_at": batch["created_at"],
            "approved_at": batch["approved_at"],
        }
    )
    record(counts(batch["counts"]))
    when.show_eta(batch.get("eta"), ui)
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
    recipients(batch.get("recipients") or [], all_rows)


def recipients(rows: list[dict], all_rows: bool) -> None:
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


def routing(batch: dict) -> str:
    routing_value = batch.get("routing") or {}
    mode = routing_value.get("mode", "auto")
    if mode == "fixed":
        return f"fixed, {routing_value.get('account') or batch.get('account_id')}"
    counted = routing_value.get("counts") or {}
    if counted:
        joined = ", ".join(f"{name} {count}" for name, count in counted.items())
        return f"auto, {joined}"
    return "auto"


def show_preview(
    preview: dict,
    ui: Ui,
    *,
    key: str | None = None,
    table_view: bool = False,
) -> None:
    messages = preview["messages"]
    if not table_view:
        cards(preview, messages[:1] if key is not None else messages, ui, key)
        when.show_capacity(preview.get("capacity"), ui)
        return
    record(
        {
            "campaign": f"{preview['campaign_name']} ({preview['campaign_key']})",
            "kind": preview["source_kind"],
            "messages": (f"{preview['total']:,} total, showing {preview['sampled']}"),
            "approval": approval(preview),
            "routing": preview_routing(preview),
            "followups": followups(preview),
            "attachments": attachments(preview),
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
    when.show_capacity(preview.get("capacity"), ui)
    for field in preview.get("ignored") or []:
        print(f"ignored: {field}")
    for warning in preview.get("warnings") or []:
        print(f"warning: {warning}")
    if not ui.quiet and preview.get("sampled", 0) < preview.get("total", 0):
        print()
        print(f"next: downcroc batch preview {preview.get('path', 'FILE')} --all")


def cards(preview: dict, messages: list[dict], ui: Ui, key: str | None) -> None:
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


def approval(preview: dict) -> str:
    if preview["valid"] != preview["total"]:
        return f"{preview['total'] - preview['valid']} invalid, nothing will submit"
    return f"{preview['valid']:,} valid"


def preview_routing(preview: dict) -> str:
    routing_value = preview.get("routing") or {}
    mode = routing_value.get("mode", "auto")
    if mode == "fixed":
        account = routing_value.get("account_id") or routing_value.get("account") or "-"
        return f"fixed, {account}, {preview['total']:,} messages"
    counted = routing_value.get("counts") or {}
    if not counted:
        return "auto, no account"
    joined = ", ".join(f"{name} {count:,}" for name, count in counted.items())
    return f"auto, {joined}"


def followups(preview: dict) -> str:
    steps = preview.get("followups") or []
    if not steps:
        return "none"
    return ", ".join(
        f"{step['key']} after {step['after_days']}d when {step['when']}"
        for step in steps
    )


def attachments(preview: dict) -> str:
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


def example(kind: str, write_to: str | None, ui: Ui) -> int:
    if not write_to:
        if ui.json_mode:
            json_out(inputs.EXAMPLES[kind])
            return 0
        for name, content in inputs.EXAMPLES[kind].items():
            print(f"# {name}")
            if isinstance(content, dict):
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


def show_schema(ui: Ui) -> int:
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
