from __future__ import annotations

from pathlib import Path

from downcroc.cli.client import api, get, post
from downcroc.cli.context import load
from downcroc.cli.output import json_out, record, table


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
        text = Path(text_file).read_text(encoding="utf-8")
    if html_file is not None:
        html = Path(html_file).read_text(encoding="utf-8")
    return text or "", html


def run(args: object) -> int:
    paths, _, _ = load()
    with api(paths) as client:
        if args.action == "list":
            rows = get(
                client,
                "/api/jobs",
                batch=getattr(args, "batch", None),
                account=getattr(args, "account", None),
                state=getattr(args, "state", None),
                limit=getattr(args, "limit", None),
            )
            if args.json:
                json_out(rows)
            else:
                _list(rows)
            return 0
        if args.action == "create":
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
                job = post(client, f"/api/jobs/{job['id']}/send")
            if args.json:
                json_out(job)
            else:
                print(f"created {job['id']} ({job['state']})")
            return 0
        if args.action == "send":
            job = post(client, f"/api/jobs/{args.job_id}/send")
            if args.json:
                json_out(job)
            else:
                print(f"{job['id']} {job['state']}")
            return 0
        job = get(client, f"/api/jobs/{args.job_id}")
        if args.json:
            json_out(job)
        else:
            _show(job)
        return 0
