from __future__ import annotations

from downcroc.cli.client import api, get, post
from downcroc.cli.context import load
from downcroc.cli.output import json_out, record, table

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


def _list(rows: list[dict]) -> None:
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


def _show(batch: dict, all_rows: bool) -> None:
    record(
        {
            "id": batch["id"],
            "name": batch["name"],
            "kind": batch["kind"],
            "state": batch["state"],
            "approval": batch["approval"],
            "source": batch["source_ref"],
            "template": batch["template_ref"],
            "created_at": batch["created_at"],
            "approved_at": batch["approved_at"],
        }
    )
    record(_counts(batch["counts"]))
    if batch.get("warnings"):
        for warning in batch["warnings"]:
            print(f"warning: {warning}")
    _recipients(batch.get("recipients") or [], all_rows)


def _preview(preview: dict) -> None:
    record(
        {
            "source": preview["source_kind"],
            "campaign": preview["campaign_name"],
            "key": preview["campaign_key"],
            "routing": preview["routing_mode"],
            "messages": len(preview["messages"]),
        }
    )
    table(
        ["recipient", "subject", "account"],
        [
            [item["email"], item["subject"], item["account_id"]]
            for item in preview["messages"]
        ],
    )
    for field in preview.get("ignored") or []:
        print(f"ignored: {field}")


def run(args: object) -> int:
    paths, _, _ = load()
    with api(paths) as client:
        if args.action == "list":
            rows = get(
                client,
                "/api/batches",
                state=getattr(args, "state", None),
                limit=getattr(args, "limit", None),
            )
            if args.json:
                json_out(rows)
            else:
                _list(rows)
            return 0
        if args.action == "preview":
            preview = post(
                client,
                "/api/batches/preview",
                {"path": str(args.path), "template": args.template},
                key=args.key,
            )
            if args.json:
                json_out(preview)
            else:
                _preview(preview)
            return 0
        if args.action == "submit":
            batch = post(
                client,
                "/api/batches",
                {"path": str(args.path), "template": args.template},
            )
            if args.approve != "none":
                batch = post(
                    client,
                    f"/api/batches/{batch['id']}/approve",
                    {"mode": args.approve},
                )
            if args.json:
                json_out(batch)
            else:
                print(f"submitted {batch['id']} ({batch['state']})")
            return 0
        if args.action == "approve":
            batch = post(
                client,
                f"/api/batches/{args.batch_id}/approve",
                {"mode": args.mode},
            )
            if args.json:
                json_out(batch)
            else:
                print(f"approved {batch['id']} ({batch['state']})")
            return 0
        if args.action == "cancel":
            batch = post(client, f"/api/batches/{args.batch_id}/cancel")
            if args.json:
                json_out(batch)
            else:
                print(f"cancelled {batch['id']} ({batch['state']})")
            return 0
        if args.action == "followup":
            batch = post(
                client,
                f"/api/batches/{args.batch_id}/followups",
                {
                    "path": str(args.path),
                    "template": args.template,
                    "step": args.step,
                    "require_approval": bool(args.require_approval),
                },
            )
            if args.json:
                json_out(batch)
            else:
                print(f"created follow-up {batch['id']} ({batch['state']})")
            return 0
        if args.action == "suppression":
            rows = get(
                client,
                f"/api/batches/{args.batch_id}/suppression-preview",
            )
            if args.json:
                json_out(rows)
            else:
                table(
                    ["address", "account", "reason"],
                    [
                        [item["address"], item["account_id"], item["reason"]]
                        for item in rows
                    ],
                )
            return 0
        batch = get(client, f"/api/batches/{args.batch_id}")
        if args.json:
            json_out(batch)
        else:
            _show(batch, bool(args.all))
        return 0
