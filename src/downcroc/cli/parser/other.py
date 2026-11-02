from __future__ import annotations

import argparse

from downcroc.cli.parser.common import LEVELS, common, day, limit, policy_flags


def top(commands: argparse._SubParsersAction) -> None:
    commands.add_parser(
        "serve",
        help="run the daemon in the foreground",
        epilog="example:\n  downcroc serve",
    )

    init = commands.add_parser(
        "init",
        help="first-run setup",
        epilog="example:\n  downcroc init",
    )
    init.add_argument("--service", action="store_true", help="install a login service")
    init.add_argument(
        "--no-service", action="store_true", help="leave the daemon detached"
    )
    init.add_argument("--account-provider", help="provider id for a mailbox")
    init.add_argument("--account-address", help="address to connect")
    common(init)

    status = commands.add_parser(
        "status",
        help="one-screen health summary",
        epilog="example:\n  downcroc status --json",
    )
    common(status)

    doctor = commands.add_parser(
        "doctor",
        help="check the installation and name fixes",
        epilog="example:\n  downcroc doctor",
    )
    doctor_actions = doctor.add_subparsers(dest="doctor_command")
    transports = doctor_actions.add_parser(
        "transports", help="check send bindings and oauth clients"
    )
    common(transports)
    capacity = doctor_actions.add_parser(
        "capacity", help="report fleet lanes, seats, and smtp-only mailboxes"
    )
    common(capacity)
    common(doctor)

    send = commands.add_parser(
        "send",
        help="guided campaign send",
        epilog=(
            "examples:\n"
            "  downcroc send\n"
            "  downcroc send campaign.json --account acct_..."
        ),
    )
    send.add_argument("path", nargs="?", help="campaign file; omit to compose one")
    send.add_argument(
        "--template", metavar="NAME|PATH", help="template name or directory"
    )
    send.add_argument("--account", metavar="ID", help="pin every message")
    send.add_argument(
        "--approve",
        choices=["none", "all"],
        default="none",
        help="none holds for review, all sends now",
    )
    common(send, yes=True)

    review = commands.add_parser(
        "review",
        help="open pending batches",
        epilog="example:\n  downcroc review",
    )
    review.add_argument("--batch", help="open one batch instead of the list")
    common(review)

    docs = commands.add_parser(
        "docs",
        help="print the installed documentation paths",
        epilog="example:\n  downcroc docs --open",
    )
    docs.add_argument("--open", action="store_true", help="open the docs index")
    common(docs)

    help_parser = commands.add_parser(
        "help",
        help="show a topic",
        epilog="examples:\n  downcroc help\n  downcroc help vault",
    )
    help_parser.add_argument("topic", nargs="?")


def files(commands: argparse._SubParsersAction) -> None:
    openapi = commands.add_parser(
        "openapi",
        help="write the OpenAPI document",
        epilog="example:\n  downcroc openapi -o openapi.json",
    )
    openapi.add_argument("-o", "--output", help="file, directory, or - for stdout")
    openapi.add_argument(
        "--mkdir",
        action="store_true",
        help="create the parent directory when it is missing",
    )
    common(openapi)

    backup = commands.add_parser(
        "backup",
        help="write a backup bundle",
        epilog="example:\n  downcroc backup ~/downcroc.zip",
    )
    backup.add_argument(
        "path",
        nargs="?",
        help="bundle file, or a directory to hold a generated bundle",
    )
    backup.add_argument("--include-logs", action="store_true")
    backup.add_argument("--force", action="store_true", help="overwrite")
    common(backup)

    restore = commands.add_parser(
        "restore",
        help="restore a backup bundle",
        epilog="example:\n  downcroc restore ~/downcroc.zip --dry-run",
    )
    restore.add_argument("path")
    restore.add_argument(
        "--dry-run", action="store_true", help="show the manifest and stop"
    )
    restore.add_argument(
        "--stop",
        action="store_true",
        help="stop the daemon, restore, then start it again",
    )
    common(restore, yes=True)


def config(commands: argparse._SubParsersAction) -> None:
    parser = commands.add_parser(
        "config",
        help="inspect and change settings",
        epilog=(
            "examples:\n"
            "  downcroc config schema\n"
            "  downcroc config set sending.jitter_min 20"
        ),
    )
    actions = parser.add_subparsers(dest="action", required=False)

    show = actions.add_parser("show", help="show the effective config")
    common(show)

    schema = actions.add_parser("schema", help="show every supported field")
    common(schema)

    set_value = actions.add_parser("set", help="set one field")
    set_value.add_argument(
        "key", nargs="?", help="dotted path, for example sending.jitter_min"
    )
    set_value.add_argument(
        "value", nargs="?", help="JSON literal or plain text; asked when omitted"
    )
    common(set_value)


def sending(commands: argparse._SubParsersAction) -> None:
    parser = commands.add_parser(
        "sending",
        help="inspect and override the global send policy",
        epilog=(
            "examples:\n"
            "  downcroc sending show\n"
            "  downcroc sending set --daily-allowance 100\n"
            "  downcroc sending set --off --for 1h\n"
            "  downcroc sending clear"
        ),
    )
    actions = parser.add_subparsers(dest="action", required=False)

    show = actions.add_parser("show", help="show the effective policy")
    common(show)

    set_value = actions.add_parser("set", help="set a service override")
    policy_flags(set_value)
    common(set_value)

    clear = actions.add_parser("clear", help="remove the service override")
    common(clear)


def stats(commands: argparse._SubParsersAction) -> None:
    parser = commands.add_parser(
        "stats",
        help="read and rebuild activity",
        epilog="example:\n  downcroc stats summary --from 2026-10-01",
    )
    actions = parser.add_subparsers(dest="action", required=True)

    for name, help_text in (
        ("summary", "show stored totals"),
        ("hourly", "show hourly activity"),
        ("daily", "show daily activity"),
        ("batches", "show batch totals"),
        ("accounts", "show account totals"),
    ):
        view = actions.add_parser(name, help=help_text)
        view.add_argument("--from", dest="from_value", type=day, help="YYYY-MM-DD")
        view.add_argument("--to", type=day, help="YYYY-MM-DD")
        view.add_argument("--account", dest="account_id", help="filter by account")
        common(view)

    pending = actions.add_parser("pending", help="show pending work and its ETA")
    common(pending)

    rebuild = actions.add_parser("rebuild", help="rebuild activity rows")
    rebuild.add_argument("--since", type=day, help="first date, YYYY-MM-DD")
    common(rebuild)

    prune = actions.add_parser("prune", help="prune expired activity rows")
    common(prune, yes=True)


def mail(commands: argparse._SubParsersAction) -> None:
    parser = commands.add_parser(
        "mail",
        help="read stored mail",
        epilog="example:\n  downcroc mail list --account acct_...",
    )
    actions = parser.add_subparsers(dest="action", required=False)

    listing = actions.add_parser("list", help="list inbox messages")
    listing.add_argument("--account", help="filter by account")
    listing.add_argument("--folder", choices=["INBOX"], help="folder")
    listing.add_argument("--thread", help="filter by thread")
    listing.add_argument(
        "--reply-state",
        choices=["confirmed", "probable", "late", "bounced"],
        help="filter by how the message answers a job",
    )
    listing.add_argument("--since", type=day, help="first date, YYYY-MM-DD")
    listing.add_argument("--until", type=day, help="last date, YYYY-MM-DD")
    limit(listing)
    common(listing)

    show = actions.add_parser("show", help="show one message")
    show.add_argument("message_id")
    common(show)

    threads = actions.add_parser("threads", help="list threads")
    threads.add_argument("--account", help="filter by account")
    threads.add_argument("--batch", help="filter by batch")
    limit(threads)
    common(threads)

    thread = actions.add_parser("thread", help="show one thread")
    thread.add_argument("thread_id")
    common(thread)

    attachment = actions.add_parser("attachment", help="download an attachment")
    attachment.add_argument("message_id")
    attachment.add_argument("attachment_id")
    attachment.add_argument(
        "-o", "--output", help="file or directory; defaults to the original name"
    )
    attachment.add_argument("--force", action="store_true", help="overwrite")
    common(attachment)


def logs(commands: argparse._SubParsersAction) -> None:
    parser = commands.add_parser(
        "logs",
        help="query the daemon log",
        epilog=(
            "examples:\n"
            "  downcroc logs --level warning --since 15m\n"
            "  downcroc logs --event watcher. --json"
        ),
    )
    parser.add_argument("--event", help="event name prefix, for example job.")
    parser.add_argument("--level", choices=LEVELS, help="minimum severity")
    parser.add_argument("--account", help="filter by account id")
    parser.add_argument("--batch", help="filter by batch id")
    parser.add_argument("--job", help="filter by job id")
    parser.add_argument("--since", help="15m, 2h, 3d, or an ISO timestamp")
    parser.add_argument(
        "--limit", type=_log_limit, default=200, help="maximum lines (1-5000)"
    )
    parser.add_argument("--follow", action="store_true", help="keep printing new lines")
    common(parser)


def _log_limit(value: str) -> int:
    try:
        number = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a whole number") from error
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    if number > 5000:
        raise argparse.ArgumentTypeError("must be at most 5000")
    return number
