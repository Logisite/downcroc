from __future__ import annotations

from downcroc.cli.client import api, get, post
from downcroc.cli.commands import when
from downcroc.cli.context import load
from downcroc.cli.output import json_out, record, table
from downcroc.cli.ui.session import Ui, build

TOTAL_KEYS = ["sent", "failed", "received", "replies", "bounces", "suppressed"]


def _totals(row: dict) -> dict:
    return {key: row.get(key, 0) for key in TOTAL_KEYS}


def _summary(data: dict) -> None:
    record({"from": data["from"], "to": data["to"], **_totals(data["total"])})
    rows = data.get("accounts") or []
    if rows:
        table(
            ["account", *TOTAL_KEYS],
            [
                [row["account_id"], *[_totals(row)[key] for key in TOTAL_KEYS]]
                for row in rows
            ],
        )


def _hourly(data: dict) -> None:
    record({"from": data["from"], "to": data["to"]})
    table(
        ["hour", "account", *TOTAL_KEYS],
        [
            [
                row["hour_start"],
                row["account_id"],
                *[_totals(row)[key] for key in TOTAL_KEYS],
            ]
            for row in data["rows"]
        ],
    )


def _daily(data: dict) -> None:
    record({"from": data["from"], "to": data["to"]})
    table(
        ["day", "account", "limit", *TOTAL_KEYS],
        [
            [
                row["day"],
                row["account_id"],
                row["quota_limit"],
                *[_totals(row)[key] for key in TOTAL_KEYS],
            ]
            for row in data["rows"]
        ],
    )


def _batches(data: dict) -> None:
    record({"from": data["from"], "to": data["to"]})
    table(
        ["batch", "name", "kind", "sent", "failed", "replies", "rate"],
        [
            [
                row["batch_id"],
                row["name"],
                row["kind"],
                row["sent"],
                row["failed"],
                row["replies"],
                row["reply_rate"],
            ]
            for row in data["rows"]
        ],
    )


def _accounts(data: dict) -> None:
    record({"from": data["from"], "to": data["to"]})
    table(
        ["account", "address", "remaining", *TOTAL_KEYS],
        [
            [
                row["account_id"],
                row["address"],
                row["remaining_allowance"],
                *[_totals(row)[key] for key in TOTAL_KEYS],
            ]
            for row in data["rows"]
        ],
    )


def _pending(data: dict, ui: Ui) -> None:
    when.show_eta(
        {
            "state": data.get("state")
            or ("blocked" if data.get("blocked_reason") else "draining"),
            "remaining": data.get("remaining"),
            "lanes": data.get("lanes"),
            "seats": data.get("seats"),
            "serial": data.get("serial"),
            "finish_at": data.get("finish_at"),
            "blocked_reason": data.get("blocked_reason"),
        },
        ui,
    )


def _range(args: object) -> dict:
    return {
        "from": getattr(args, "from_value", None),
        "to": getattr(args, "to", None),
        "account_id": getattr(args, "account_id", None),
    }


def run(args: object) -> int:
    paths, _, _ = load()
    ui = build(args)
    with api(paths) as client:
        if args.action == "summary":
            data = get(client, "/api/stats/summary", **_range(args))
            pending = get(client, "/api/stats/pending")
            if args.json:
                json_out({**data, "pending_eta": pending})
            else:
                _summary(data)
                _pending(pending, ui)
            return 0
        if args.action == "pending":
            data = get(client, "/api/stats/pending")
            if args.json:
                json_out(data)
            else:
                _pending(data, ui)
            return 0
        if args.action == "hourly":
            data = get(client, "/api/stats/hourly", **_range(args))
            if args.json:
                json_out(data)
            else:
                _hourly(data)
            return 0
        if args.action == "daily":
            data = get(client, "/api/stats/daily", **_range(args))
            if args.json:
                json_out(data)
            else:
                _daily(data)
            return 0
        if args.action == "batches":
            data = get(client, "/api/stats/batches", **_range(args))
            if args.json:
                json_out(data)
            else:
                _batches(data)
            return 0
        if args.action == "accounts":
            data = get(client, "/api/stats/accounts", **_range(args))
            if args.json:
                json_out(data)
            else:
                _accounts(data)
            return 0
        if args.action == "prune":
            result = post(client, "/api/stats/prune")
            if args.json:
                json_out(result)
            else:
                record({"bytes": result["bytes"], **result["tables"]})
            return 0
        result = post(
            client,
            "/api/stats/rebuild",
            {"since": getattr(args, "since", None)},
        )
        if args.json:
            json_out(result)
        else:
            print(
                "rebuilt {rows} rows in {duration_ms} ms".format(
                    rows=result["rows"],
                    duration_ms=result["duration_ms"],
                )
            )
        return 0
