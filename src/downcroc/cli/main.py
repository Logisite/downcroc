from __future__ import annotations

import argparse
import sys
from pathlib import Path

from downcroc.version import __version__

LEVELS = ["debug", "info", "warning", "error"]


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

    openapi = commands.add_parser("openapi", help="write the OpenAPI document")
    openapi.add_argument("-o", "--output", type=Path)

    backup = commands.add_parser("backup", help="write a backup bundle")
    backup.add_argument("path", type=Path)
    backup.add_argument("--include-logs", action="store_true")

    restore = commands.add_parser("restore", help="restore a backup bundle")
    restore.add_argument("path", type=Path)

    stats = commands.add_parser("stats", help="rebuild stored activity")
    stats_commands = stats.add_subparsers(dest="stats_command", metavar="action")
    stats_rebuild = stats_commands.add_parser("rebuild", help="rebuild activity rows")
    stats_rebuild.add_argument("--since", help="first date to rebuild, YYYY-MM-DD")

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


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "serve":
        from downcroc.cli.commands import serve

        serve.run()
        return 0
    if args.command == "service":
        from downcroc.cli.commands import service

        return service.run(args.action)
    if args.command == "openapi":
        from downcroc.cli.commands import openapi

        return openapi.run(args.output)
    if args.command == "backup":
        from downcroc.cli.commands import backup

        return backup.run(args.path, args.include_logs)
    if args.command == "restore":
        from downcroc.cli.commands import restore

        return restore.run(args.path)
    if args.command == "logs":
        from downcroc.cli.commands import logs

        return logs.run(args)
    if args.command == "stats":
        from downcroc.cli.commands import stats

        if args.stats_command == "rebuild":
            return stats.rebuild(args.since)
        build_parser().parse_args(["stats", "--help"])
        return 2

    from downcroc.cli.commands import service

    status = service.run("status")
    if status == 0:
        print("start it with: downcroc service start")
    return status


if __name__ == "__main__":
    sys.exit(main())
