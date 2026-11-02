from __future__ import annotations

from collections.abc import Callable

from downcroc.cli import output
from downcroc.cli.commands import (
    accounts,
    auth,
    backup,
    batches,
    config,
    docs,
    failed,
    help,
    init,
    jobs,
    logs,
    mail,
    openapi,
    providers,
    restore,
    review,
    send,
    sending,
    serve,
    service,
    state,
    stats,
    templates,
    uninstall,
    update,
    vault,
)
from downcroc.cli.parser import build_parser

Handler = Callable[[object], int]

HANDLERS: dict[str, Handler] = {
    "init": init.run,
    "help": help.run,
    "status": state.run,
    "doctor": state.run,
    "send": send.run,
    "review": review.run,
    "docs": docs.run,
    "service": service.run,
    "openapi": openapi.run,
    "backup": backup.run,
    "restore": restore.run,
    "auth": auth.run,
    "vault": vault.run,
    "provider": providers.run,
    "account": accounts.run,
    "batch": batches.run,
    "template": templates.run,
    "job": jobs.run,
    "failed": failed.run,
    "config": config.run,
    "sending": sending.run,
    "stats": stats.run,
    "mail": mail.run,
    "logs": logs.run,
    "update": update.run,
    "uninstall": uninstall.run,
}


def dispatch(args: object) -> int:
    command = getattr(args, "command", None)
    if command == "serve":
        serve.run()
        return 0
    if command is None:
        return state.run(args)
    handler = HANDLERS.get(command)
    if handler is None:
        raise KeyError(command)
    return handler(args)


def configure(args: object) -> None:
    output.configure(
        wide=bool(getattr(args, "wide", False)),
        full=bool(getattr(args, "full", False)),
    )


def run(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    configure(args)
    return dispatch(args)
