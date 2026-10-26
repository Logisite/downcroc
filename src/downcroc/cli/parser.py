from __future__ import annotations

import argparse
from pathlib import Path

from downcroc.version import __version__

LEVELS = ["debug", "info", "warning", "error"]


def _json(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="print JSON")


def _limit(parser: argparse.ArgumentParser, default: int = 100) -> None:
    parser.add_argument("--limit", type=int, default=default)


def _stats_range(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--from", dest="from_value", help="first day, YYYY-MM-DD")
    parser.add_argument("--to", help="last day, YYYY-MM-DD")
    parser.add_argument("--account", dest="account_id")
    _json(parser)


def _auth(commands: argparse._SubParsersAction) -> None:
    auth = commands.add_parser("auth", help="inspect daemon authentication")
    actions = auth.add_subparsers(dest="action", required=True)
    status = actions.add_parser("status", help="check the daemon token")
    _json(status)


def _vault(commands: argparse._SubParsersAction) -> None:
    vault = commands.add_parser("vault", help="inspect and control the vault")
    actions = vault.add_subparsers(dest="action", required=True)
    status = actions.add_parser("status", help="show the vault state")
    _json(status)
    unlock = actions.add_parser("unlock", help="unlock the vault")
    unlock.add_argument(
        "--password-stdin",
        action="store_true",
        help="read the password from stdin",
    )
    _json(unlock)
    lock = actions.add_parser("lock", help="lock the vault")
    _json(lock)


def _account(commands: argparse._SubParsersAction) -> None:
    account = commands.add_parser("account", help="manage mail accounts")
    actions = account.add_subparsers(dest="action", required=True)

    listing = actions.add_parser("list", help="list accounts")
    _json(listing)

    show = actions.add_parser("show", help="show one account")
    show.add_argument("account_id")
    _json(show)

    add = actions.add_parser("add", help="create a pending account")
    add.add_argument("--provider", required=True)
    add.add_argument("--address", required=True)
    add.add_argument("--label", default="")
    _json(add)

    remove = actions.add_parser("delete", help="delete an account")
    remove.add_argument("account_id")
    remove.add_argument("--yes", action="store_true", help="skip confirmation")

    providers = actions.add_parser("providers", help="list provider declarations")
    _json(providers)

    attempt = actions.add_parser("attempt", help="start an OAuth connect attempt")
    attempt.add_argument("account_id")
    attempt.add_argument(
        "--wait",
        action="store_true",
        help="wait for the account to connect",
    )
    attempt.add_argument("--timeout", type=float, default=180.0)
    _json(attempt)

    connect = actions.add_parser("connect", help="connect an app password account")
    connect.add_argument("account_id")
    connect.add_argument("--password-stdin", action="store_true")
    _json(connect)

    verify = actions.add_parser("verify", help="verify an account login")
    verify.add_argument("account_id")
    verify.add_argument("--refresh", action="store_true")
    _json(verify)

    sync = actions.add_parser("sync", help="request an INBOX sync")
    sync.add_argument("account_id")
    _json(sync)

    watch = actions.add_parser("watch", help="enable or disable the watcher")
    watch.add_argument("account_id")
    state = watch.add_mutually_exclusive_group(required=True)
    state.add_argument("--on", action="store_true", dest="enabled")
    state.add_argument("--off", action="store_false", dest="enabled")
    _json(watch)


def _batch(commands: argparse._SubParsersAction) -> None:
    batch = commands.add_parser("batch", help="submit and manage batches")
    actions = batch.add_subparsers(dest="action", required=True)

    listing = actions.add_parser("list", help="list batches")
    listing.add_argument("--state")
    _limit(listing)
    _json(listing)

    show = actions.add_parser("show", help="show a batch and its recipients")
    show.add_argument("batch_id")
    show.add_argument("--all", action="store_true", help="show every recipient")
    _json(show)

    preview = actions.add_parser("preview", help="preview an input file")
    preview.add_argument("path", type=Path)
    preview.add_argument("--template")
    preview.add_argument("--key")
    _json(preview)

    submit = actions.add_parser("submit", help="submit an input file")
    submit.add_argument("path", type=Path)
    submit.add_argument("--template")
    submit.add_argument(
        "--approve",
        choices=["none", "one", "all"],
        default="none",
    )
    _json(submit)

    approve = actions.add_parser("approve", help="approve a batch")
    approve.add_argument("batch_id")
    approve.add_argument("--mode", choices=["one", "all"], default="all")
    _json(approve)

    cancel = actions.add_parser("cancel", help="cancel a batch")
    cancel.add_argument("batch_id")
    _json(cancel)

    followup = actions.add_parser("followup", help="create a follow-up step")
    followup.add_argument("batch_id")
    followup.add_argument("path", type=Path)
    followup.add_argument("--step", required=True)
    followup.add_argument("--template")
    followup.add_argument("--require-approval", action="store_true")
    _json(followup)

    suppression = actions.add_parser("suppression", help="show suppressed recipients")
    suppression.add_argument("batch_id")
    _json(suppression)


def _job(commands: argparse._SubParsersAction) -> None:
    job = commands.add_parser("job", help="inspect and send jobs")
    actions = job.add_subparsers(dest="action", required=True)

    listing = actions.add_parser("list", help="list jobs")
    listing.add_argument("--batch")
    listing.add_argument("--account")
    listing.add_argument("--state")
    _limit(listing)
    _json(listing)

    show = actions.add_parser("show", help="show one job")
    show.add_argument("job_id")
    _json(show)

    send = actions.add_parser("send", help="send one job now")
    send.add_argument("job_id")
    _json(send)

    create = actions.add_parser("create", help="create a manual job")
    create.add_argument("--account", required=True, dest="account_id")
    create.add_argument("--to", required=True, dest="recipient")
    create.add_argument("--name", dest="recipient_name")
    create.add_argument("--subject", required=True)
    text = create.add_mutually_exclusive_group()
    text.add_argument("--text")
    text.add_argument("--text-file", type=Path)
    html = create.add_mutually_exclusive_group()
    html.add_argument("--html")
    html.add_argument("--html-file", type=Path)
    create.add_argument("--batch", default="manual")
    create.add_argument("--send", action="store_true")
    _json(create)


def _failed(commands: argparse._SubParsersAction) -> None:
    failed = commands.add_parser("failed", help="inspect and retry failures")
    actions = failed.add_subparsers(dest="action", required=True)

    listing = actions.add_parser("list", help="list failed jobs")
    _limit(listing)
    _json(listing)

    show = actions.add_parser("show", help="show one failure")
    show.add_argument("job_id")
    _json(show)

    retry = actions.add_parser("retry", help="retry one failure")
    retry.add_argument("job_id")
    _json(retry)

    retry_all = actions.add_parser("retry-all", help="retry every failure")
    _json(retry_all)


def _config(commands: argparse._SubParsersAction) -> None:
    config = commands.add_parser("config", help="inspect and change settings")
    actions = config.add_subparsers(dest="action", required=True)

    show = actions.add_parser("show", help="show the effective config")
    _json(show)

    schema = actions.add_parser("schema", help="show every supported field")
    _json(schema)

    set_value = actions.add_parser("set", help="set one field")
    set_value.add_argument("key", help="dotted path, for example sending.jitter_min")
    set_value.add_argument("value", help="JSON literal or plain text")
    _json(set_value)


def _stats(commands: argparse._SubParsersAction) -> None:
    stats = commands.add_parser("stats", help="read and rebuild activity")
    actions = stats.add_subparsers(dest="action", required=True)

    summary = actions.add_parser("summary", help="show stored totals")
    _stats_range(summary)

    hourly = actions.add_parser("hourly", help="show hourly activity")
    _stats_range(hourly)

    daily = actions.add_parser("daily", help="show daily activity")
    _stats_range(daily)

    batches = actions.add_parser("batches", help="show batch totals")
    _stats_range(batches)

    accounts = actions.add_parser("accounts", help="show account totals")
    _stats_range(accounts)

    rebuild = actions.add_parser("rebuild", help="rebuild activity rows")
    rebuild.add_argument("--since", help="first date to rebuild, YYYY-MM-DD")
    _json(rebuild)

    prune = actions.add_parser("prune", help="prune expired activity rows")
    _json(prune)


def _mail(commands: argparse._SubParsersAction) -> None:
    mail = commands.add_parser("mail", help="read stored mail")
    actions = mail.add_subparsers(dest="action", required=True)

    listing = actions.add_parser("list", help="list inbox messages")
    listing.add_argument("--account")
    listing.add_argument("--folder")
    listing.add_argument("--thread")
    listing.add_argument("--reply-state")
    listing.add_argument("--since")
    listing.add_argument("--until")
    listing.add_argument("--offset", type=int, default=0)
    _limit(listing)
    _json(listing)

    show = actions.add_parser("show", help="show one message")
    show.add_argument("message_id")
    _json(show)

    threads = actions.add_parser("threads", help="list threads")
    threads.add_argument("--account")
    threads.add_argument("--batch")
    threads.add_argument("--offset", type=int, default=0)
    _limit(threads)
    _json(threads)

    thread = actions.add_parser("thread", help="show one thread")
    thread.add_argument("thread_id")
    _json(thread)

    attachment = actions.add_parser("attachment", help="download an attachment")
    attachment.add_argument("message_id")
    attachment.add_argument("attachment_id")
    attachment.add_argument("-o", "--output", type=Path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="downcroc",
        description="local email orchestration daemon",
    )
    parser.add_argument(
        "--version", action="version", version=f"downcroc {__version__}"
    )
    commands = parser.add_subparsers(dest="command", metavar="command")

    commands.add_parser("serve", help="run the daemon in the foreground")

    service = commands.add_parser("service", help="control the running daemon")
    service.add_argument("action", choices=["start", "stop", "status"])
    _json(service)

    openapi = commands.add_parser("openapi", help="write the OpenAPI document")
    openapi.add_argument("-o", "--output", type=Path)

    backup = commands.add_parser("backup", help="write a backup bundle")
    backup.add_argument(
        "path",
        type=Path,
        nargs="?",
        help="bundle file, or a directory to hold a generated bundle",
    )
    backup.add_argument("--include-logs", action="store_true")

    restore = commands.add_parser("restore", help="restore a backup bundle")
    restore.add_argument("path", type=Path)

    _auth(commands)
    _vault(commands)
    _account(commands)
    _batch(commands)
    _job(commands)
    _failed(commands)
    _config(commands)
    _stats(commands)
    _mail(commands)

    logs = commands.add_parser("logs", help="query the daemon log")
    logs.add_argument("--event", help="event name prefix, for example job.")
    logs.add_argument("--level", choices=LEVELS)
    logs.add_argument("--account")
    logs.add_argument("--batch")
    logs.add_argument("--job")
    logs.add_argument("--since", help="15m, 2h, 3d, or an ISO timestamp")
    logs.add_argument("--limit", type=int, default=200)
    logs.add_argument("--follow", action="store_true")
    logs.add_argument("--json", action="store_true")
    return parser
