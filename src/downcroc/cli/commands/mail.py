from __future__ import annotations

from email.message import Message
from pathlib import Path

from downcroc.cli import paths as path_tools
from downcroc.cli.client import api, bytes_of, get, get_page, post
from downcroc.cli.context import load
from downcroc.cli.output import json_out, page_footer, record, table
from downcroc.cli.ui import prompts
from downcroc.cli.ui.menu import open_menu
from downcroc.cli.ui.session import Ui, build

REPLY_WORDS = {
    "confirmed": ("confirmed reply", "headers prove it answers a job"),
    "probable": ("likely reply", "subject and participant match, headers do not"),
    "late": ("late reply", "arrived after the reply window"),
    "bounced": ("bounce", "a delivery failure, not a person"),
}
_EXPLAINED: set[str] = set()


def _reply(value: str | None) -> str:
    if not value:
        return "-"
    return REPLY_WORDS.get(value, (value, ""))[0]


def _explain(rows: list[dict]) -> None:
    seen = {row["reply_state"] for row in rows if row.get("reply_state") in REPLY_WORDS}
    fresh = sorted(seen - _EXPLAINED)
    if not fresh:
        return
    print()
    width = max(len(REPLY_WORDS[name][0]) for name in fresh)
    for name in fresh:
        word, meaning = REPLY_WORDS[name]
        print(f"  {word.ljust(width)}  {meaning}")
        _EXPLAINED.add(name)


def _messages(rows: list[dict]) -> None:
    table(
        ["date", "from", "subject", "reply", "attachments", "id"],
        [
            [
                row["date"],
                row["from_address"],
                row["subject"],
                _reply(row["reply_state"]),
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
            "reply": _reply(message["reply_state"]),
            "thread": message["thread_id"],
            "job": message["job_id"],
            "dsn": message["is_dsn"],
            "attachments": len(message["attachments"]),
        }
    )
    for attachment in message["attachments"]:
        print(
            f"  {attachment['id']}  {attachment['filename']}  "
            f"{attachment['size']} bytes"
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


def _destination(output: str | None, name: str) -> Path:
    if output is None:
        return Path(name).absolute()
    target = path_tools.expand(output)
    if target.is_dir() or str(output).endswith(("/", "\\")):
        target.mkdir(parents=True, exist_ok=True)
        return target / name
    return target


def _save(args: object, ui: Ui, payload: bytes, disposition: str | None) -> int:
    destination = _destination(getattr(args, "output", None), _filename(disposition))
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not getattr(args, "force", False):
        prompts.confirm(
            f"overwrite {destination}?",
            ui=ui,
            default=False,
        )
    destination.write_bytes(payload)
    if ui.json_mode:
        json_out({"path": str(destination), "bytes": len(payload)})
    else:
        print(f"wrote {destination} ({len(payload)} bytes)")
    return 0


def _listing(client, args: object, ui: Ui) -> int:
    rows, total = get_page(
        client,
        "/api/messages",
        account=getattr(args, "account", None),
        folder=getattr(args, "folder", None),
        thread=getattr(args, "thread", None),
        reply_state=getattr(args, "reply_state", None),
        since=getattr(args, "since", None),
        until=getattr(args, "until", None),
        limit=getattr(args, "limit", None) or 100,
        offset=getattr(args, "offset", 0) or 0,
    )
    if ui.json_mode:
        json_out(rows)
        return 0
    _messages(rows)
    _explain(rows)
    page_footer(
        len(rows),
        total,
        limit=getattr(args, "limit", None) or 100,
        offset=getattr(args, "offset", 0) or 0,
    )
    return 0


def _thread_listing(client, args: object, ui: Ui) -> int:
    rows, total = get_page(
        client,
        "/api/threads",
        account=getattr(args, "account", None),
        batch=getattr(args, "batch", None),
        limit=getattr(args, "limit", None) or 100,
        offset=getattr(args, "offset", 0) or 0,
    )
    if ui.json_mode:
        json_out(rows)
        return 0
    _threads(rows)
    page_footer(
        len(rows),
        total,
        limit=getattr(args, "limit", None) or 100,
        offset=getattr(args, "offset", 0) or 0,
    )
    return 0


def _thread(client, args: object, ui: Ui) -> int:
    detail = get(client, f"/api/threads/{args.thread_id}")
    if ui.json_mode:
        json_out(detail)
        return 0
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
    _explain(detail["messages"])
    return 0


def _prune(client, args: object, ui: Ui) -> int:
    dry_run = bool(getattr(args, "dry_run", False))
    if not dry_run:
        prompts.confirm(
            "remove inbox copies of mail sent by your own accounts?",
            ui=ui,
            yes_flag=bool(getattr(args, "yes", False)),
        )
    result = post(
        client,
        "/api/messages/prune",
        {
            "account_id": getattr(args, "account", None),
            "dry_run": dry_run,
            "confirm": not dry_run,
        },
    )
    if ui.json_mode:
        json_out(result)
        return 0
    verb = "would remove" if result["dry_run"] else "removed"
    print(f"{verb} {result['messages']} messages ({result['bytes']} bytes)")
    if not result.get("stats_rebuilt", True):
        print("activity counters could not be rebuilt; run downcroc stats rebuild")
    return 0


def run(args: object) -> int:
    ui = build(args)
    paths, _, _ = load()
    action = getattr(args, "action", None)
    if action is None and open_menu(ui, "mail_menu"):
        return 0
    with api(paths) as client:
        if action in {None, "list"}:
            return _listing(client, args, ui)
        if action == "threads":
            return _thread_listing(client, args, ui)
        if action == "attachment":
            payload, disposition = bytes_of(
                client,
                f"/api/messages/{args.message_id}/attachments/{args.attachment_id}",
            )
            return _save(args, ui, payload, disposition)
        if action == "thread":
            return _thread(client, args, ui)
        if action == "prune":
            return _prune(client, args, ui)
        message = get(client, f"/api/messages/{args.message_id}")
        if ui.json_mode:
            json_out(message)
        else:
            _message(message)
        return 0
