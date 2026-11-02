from __future__ import annotations

from downcroc.cli.ui import prompts
from downcroc.cli.ui.data import action, need_daemon, rows
from downcroc.cli.ui.menu import Item, quit_menu, run, run_args
from downcroc.cli.ui.session import Ui


def template_menu(ui: Ui) -> None:
    run(
        ui,
        "Templates",
        [
            Item("List templates", action=action(ui, "template", "list")),
            Item(
                "Show a template",
                detail="ask for the name",
                action=lambda: run_args(
                    ui,
                    "template",
                    "show",
                    prompts.ask("Template name", ui=ui, field="NAME"),
                ),
            ),
            Item(
                "Create a template",
                action=lambda: run_args(
                    ui,
                    "template",
                    "new",
                    prompts.ask("Template name", ui=ui, default="intro", field="NAME"),
                ),
            ),
            Item(
                "Validate a template",
                action=lambda: run_args(
                    ui,
                    "template",
                    "validate",
                    prompts.ask("Template name or directory", ui=ui, field="NAME"),
                ),
            ),
            Item("Quit", action=quit_menu),
        ],
    )


def _failed_items(ui: Ui, verb: str) -> list[Item]:
    found = rows(ui, "/api/failed")
    if found is None:
        return need_daemon(ui)
    if not found:
        return [Item("No failures", detail="every job is moving")]
    return [
        Item(
            row["recipient"],
            detail=f"{row['code']}  {row['job_id']}",
            action=action(ui, "failed", verb, row["job_id"]),
        )
        for row in found
    ]


def _retry_all(ui: Ui) -> None:
    if prompts.confirm("Retry every failure?", ui=ui):
        run_args(ui, "failed", "retry-all", "--yes")


def failed_menu(ui: Ui) -> None:
    run(
        ui,
        "Failures",
        [
            Item("List failures", action=action(ui, "failed", "list")),
            Item("Show a failure", children=_failed_items(ui, "show")),
            Item("Retry one", children=_failed_items(ui, "retry")),
            Item(
                "Retry all",
                detail="asks before queueing",
                action=lambda: _retry_all(ui),
            ),
            Item("Quit", action=quit_menu),
        ],
    )


def _message_items(ui: Ui, verb: str, path: str) -> list[Item]:
    found = rows(ui, path)
    if found is None:
        return need_daemon(ui)
    if not found:
        return [Item("No mail yet", detail="sync an account first")]
    return [
        Item(
            str(row.get("subject") or row["id"]),
            detail=f"{row.get('from_address', '')}  {row['id']}",
            action=action(ui, "mail", verb, row["id"]),
        )
        for row in found
    ]


def mail_menu(ui: Ui) -> None:
    run(
        ui,
        "Mail",
        [
            Item("List inbox", action=action(ui, "mail", "list")),
            Item(
                "Show a message", children=_message_items(ui, "show", "/api/messages")
            ),
            Item("List threads", action=action(ui, "mail", "threads")),
            Item(
                "Show a thread", children=_message_items(ui, "thread", "/api/threads")
            ),
            Item("Quit", action=quit_menu),
        ],
    )


def _backup(ui: Ui) -> None:
    path = prompts.ask(
        "Bundle path (blank for a generated name)", ui=ui, required=False
    )
    if path:
        run_args(ui, "backup", path)
    else:
        run_args(ui, "backup")


def _restore(ui: Ui) -> None:
    path = prompts.ask("Bundle path", ui=ui, field="FILE")
    mode = prompts.choose(
        "Restore",
        [
            prompts.Option("Check the bundle", "check", "verify without writing"),
            prompts.Option("Restore", "restore", "stop the daemon, then restore"),
            prompts.Option("Restore and start", "start", "restore, then start again"),
        ],
        ui=ui,
        default=0,
        back=False,
    )
    if mode == "check":
        run_args(ui, "restore", path, "--dry-run")
        return
    prompts.confirm_word(
        "restore", f"This replaces the current state with {path}.", ui=ui
    )
    argv = ["restore", path, "--yes"]
    if mode == "start":
        argv.append("--stop")
    run_args(ui, *argv)


def backup_menu(ui: Ui) -> None:
    run(
        ui,
        "Back up or restore",
        [
            Item("Write a backup", action=lambda: _backup(ui)),
            Item(
                "Restore a bundle",
                detail="asks before replacing",
                action=lambda: _restore(ui),
            ),
            Item("Quit", action=quit_menu),
        ],
    )
