from __future__ import annotations

import sys
from types import SimpleNamespace

from downcroc.cli.client import CliError
from downcroc.cli.parser import build_parser
from downcroc.runtime.config.loader import ConfigError


def _dispatch(args: object) -> int:
    if args.command == "serve":
        from downcroc.cli.commands import serve

        serve.run()
        return 0
    if args.command == "service":
        from downcroc.cli.commands import service

        return service.run(args)
    if args.command == "openapi":
        from downcroc.cli.commands import openapi

        return openapi.run(args.output)
    if args.command == "auth":
        from downcroc.cli.commands import auth

        return auth.run(args)
    if args.command == "backup":
        from downcroc.cli.commands import backup

        return backup.run(args.path, args.include_logs)
    if args.command == "restore":
        from downcroc.cli.commands import restore

        return restore.run(args.path)
    if args.command == "logs":
        from downcroc.cli.commands import logs

        return logs.run(args)
    if args.command == "vault":
        from downcroc.cli.commands import vault

        return vault.run(args)
    if args.command == "account":
        from downcroc.cli.commands import accounts

        return accounts.run(args)
    if args.command == "batch":
        from downcroc.cli.commands import batches

        return batches.run(args)
    if args.command == "job":
        from downcroc.cli.commands import jobs

        return jobs.run(args)
    if args.command == "failed":
        from downcroc.cli.commands import failed

        return failed.run(args)
    if args.command == "config":
        from downcroc.cli.commands import config

        return config.run(args)
    if args.command == "stats":
        from downcroc.cli.commands import stats

        return stats.run(args)
    if args.command == "mail":
        from downcroc.cli.commands import mail

        return mail.run(args)
    from downcroc.cli.commands import service

    status = service.run(SimpleNamespace(action="status", json=False))
    if status == 0:
        print("start it with: downcroc service start")
    return status


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return _dispatch(args)
    except CliError as error:
        print(f"error: {error}", file=sys.stderr)
        for key, value in error.fields.items():
            print(f"  {key}: {value}", file=sys.stderr)
        return 1
    except ConfigError as error:
        detail = f"{error.field}: {error}" if error.field else str(error)
        print(f"config error: {detail}", file=sys.stderr)
        return 1
    except OSError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
