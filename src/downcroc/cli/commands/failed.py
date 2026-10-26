from __future__ import annotations

from downcroc.cli.client import api, get, post
from downcroc.cli.context import load
from downcroc.cli.output import json_out, record, table


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


def run(args: object) -> int:
    paths, _, _ = load()
    with api(paths) as client:
        if args.action == "list":
            rows = get(
                client,
                "/api/failed",
                limit=getattr(args, "limit", None),
            )
            if args.json:
                json_out(rows)
            else:
                _list(rows)
            return 0
        if args.action == "retry-all":
            result = post(client, "/api/failed/retry")
            if args.json:
                json_out(result)
            else:
                print(f"retried {result['retried']} failures")
            return 0
        if args.action == "retry":
            job = post(client, f"/api/failed/{args.job_id}/retry")
            if args.json:
                json_out(job)
            else:
                print(f"retried {job['id']} ({job['state']})")
            return 0
        item = get(client, f"/api/failed/{args.job_id}")
        if args.json:
            json_out(item)
        else:
            _show(item)
        return 0
