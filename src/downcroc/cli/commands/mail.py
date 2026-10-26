from __future__ import annotations

from email.message import Message
from pathlib import Path

from downcroc.cli.client import api, bytes_of, get
from downcroc.cli.context import load
from downcroc.cli.output import json_out, record, table


def _messages(rows: list[dict]) -> None:
    table(
        ["date", "from", "subject", "reply", "attachments", "id"],
        [
            [
                row["date"],
                row["from_address"],
                row["subject"],
                row["reply_state"],
                row["attachment_count"],
                row["id"],
            ]
            for row in rows
        ],
    )


def _message(message: dict) -> None:
    record(
        {
            "id": message["id"],
            "account": message["account_id"],
            "folder": message["folder"],
            "uid": message["uid"],
            "message_id": message["message_id"],
            "from": message["from_address"],
            "to": ", ".join(message["to"]),
            "subject": message["subject"],
            "date": message["date"],
            "reply_state": message["reply_state"],
            "thread": message["thread_id"],
            "job": message["job_id"],
            "dsn": message["is_dsn"],
        }
    )
    attachments = message.get("attachments") or []
    if attachments:
        table(
            ["attachment", "type", "size", "inline"],
            [
                [
                    item["filename"],
                    item["content_type"],
                    item["size"],
                    item["inline"],
                ]
                for item in attachments
            ],
        )
    body = message.get("body_text")
    if body:
        print()
        print(body)
        if message.get("body_truncated"):
            print("[body truncated]")
    else:
        print()
        print("(no text body)")


def _threads(rows: list[dict]) -> None:
    table(
        ["id", "subject", "messages", "replies", "last_seen"],
        [
            [
                row["id"],
                row["subject"],
                row["message_count"],
                row["reply_count"],
                row["last_seen"],
            ]
            for row in rows
        ],
    )


def _filename(disposition: str | None) -> str:
    if not disposition:
        return "attachment"
    message = Message()
    message["Content-Disposition"] = disposition
    found = message.get_filename()
    if not found:
        return "attachment"
    name = Path(found).name
    return name or "attachment"


def _destination(output: Path | None, name: str) -> Path:
    if output is None:
        return Path(name)
    output = output.expanduser()
    if output.is_dir():
        return output / name
    return output


def run(args: object) -> int:
    paths, _, _ = load()
    with api(paths) as client:
        if args.action == "list":
            rows = get(
                client,
                "/api/messages",
                account=getattr(args, "account", None),
                folder=getattr(args, "folder", None),
                thread=getattr(args, "thread", None),
                reply_state=getattr(args, "reply_state", None),
                since=getattr(args, "since", None),
                until=getattr(args, "until", None),
                limit=getattr(args, "limit", None),
                offset=getattr(args, "offset", None),
            )
            if args.json:
                json_out(rows)
            else:
                _messages(rows)
            return 0
        if args.action == "threads":
            rows = get(
                client,
                "/api/threads",
                account=getattr(args, "account", None),
                batch=getattr(args, "batch", None),
                limit=getattr(args, "limit", None),
                offset=getattr(args, "offset", None),
            )
            if args.json:
                json_out(rows)
            else:
                _threads(rows)
            return 0
        if args.action == "attachment":
            payload, disposition = bytes_of(
                client,
                f"/api/messages/{args.message_id}/attachments/{args.attachment_id}",
            )
            destination = _destination(args.output, _filename(disposition))
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
            print(f"wrote {destination} ({len(payload)} bytes)")
            return 0
        if args.action == "thread":
            detail = get(client, f"/api/threads/{args.thread_id}")
            if args.json:
                json_out(detail)
            else:
                thread = detail["thread"]
                record(
                    {
                        "id": thread["id"],
                        "subject": thread["subject"],
                        "batch": thread["batch_id"],
                        "messages": thread["message_count"],
                        "replies": thread["reply_count"],
                        "first_seen": thread["first_seen"],
                        "last_seen": thread["last_seen"],
                    }
                )
                _messages(detail["messages"])
            return 0
        message = get(client, f"/api/messages/{args.message_id}")
        if args.json:
            json_out(message)
        else:
            _message(message)
        return 0
