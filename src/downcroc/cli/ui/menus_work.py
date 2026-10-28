from __future__ import annotations

from downcroc.cli.ui import prompts
from downcroc.cli.ui.data import action, need_daemon, rows
from downcroc.cli.ui.menu import Item, quit_menu, run, run_args
from downcroc.cli.ui.session import Ui


def _ask_path(ui: Ui, label: str) -> str:
    return prompts.ask(label, ui=ui, field="FILE")


def _batch_items(ui: Ui, verb: str) -> list[Item]:
    found = rows(ui, "/api/batches")
    if found is None:
        return need_daemon(ui)
    if not found:
        return [Item("No batches yet", detail="submit a campaign first")]
    return [
        Item(
            row["name"],
            detail=f"{row['state']}  {row['counts'].get('sent', 0)} sent  {row['id']}",
            action=action(ui, "batch", verb, row["id"]),
        )
        for row in found
    ]


def _validate(ui: Ui) -> None:
    run_args(ui, "batch", "validate", _ask_path(ui, "Campaign file or CSV"))


def _preview(ui: Ui) -> None:
    run_args(ui, "batch", "preview", _ask_path(ui, "Campaign file or CSV"))


def _submit(ui: Ui) -> None:
    path = _ask_path(ui, "Campaign file or CSV")
    mode = prompts.choose(
        "Approval",
        [
            prompts.Option("Hold for review", "none", "approve later"),
            prompts.Option("Send now", "all", "no second look"),
            prompts.Option("Send one first", "one", "a sample, then the rest"),
        ],
        ui=ui,
        default=0,
        back=False,
    )
    run_args(ui, "batch", "submit", path, "--approve", str(mode))


def _approve_items(ui: Ui) -> list[Item]:
    found = rows(ui, "/api/batches", state="awaiting_approval")
    if found is None:
        return need_daemon(ui)
    if not found:
        return [Item("Nothing is waiting", detail="no batch needs approval")]
    return [
        Item(
            row["name"],
            detail=f"{row['counts'].get('pending', 0)} pending  {row['id']}",
            action=lambda row=row: _approve(ui, row),
        )
        for row in found
    ]


def _approve(ui: Ui, row: dict) -> None:
    mode = prompts.choose(
        f"Approve {row['name']}",
        [
            prompts.Option("Send one first", "one", "a sample"),
            prompts.Option("Send all", "all", "the rest of the batch"),
        ],
        ui=ui,
        default=0,
        back=False,
    )
    if prompts.confirm(f"Approve {row['name']} now?", ui=ui):
        run_args(ui, "batch", "approve", row["id"], "--mode", str(mode), "--yes")


def _cancel(ui: Ui, row: dict) -> None:
    if prompts.confirm(f"Cancel {row['name']}?", ui=ui, default=False):
        run_args(ui, "batch", "cancel", row["id"], "--yes")


def _cancel_items(ui: Ui) -> list[Item]:
    found = rows(ui, "/api/batches")
    if found is None:
        return need_daemon(ui)
    return [
        Item(
            row["name"],
            detail=f"{row['state']}  {row['id']}",
            action=lambda row=row: _cancel(ui, row),
        )
        for row in found
        if row["state"] not in {"done", "cancelled"}
    ]


def _followup(ui: Ui) -> None:
    found = rows(ui, "/api/batches")
    if found is None:
        return
    batch = prompts.choose(
        "Follow up on a batch",
        [prompts.Option(row["name"], row["id"], row["state"]) for row in found],
        ui=ui,
        back=False,
    )
    path = _ask_path(ui, "Follow-up campaign file")
    step = prompts.ask("Step id", ui=ui, field="--step")
    run_args(ui, "batch", "followup", str(batch), path, "--step", step)


def batch_menu(ui: Ui) -> None:
    run(
        ui,
        "Batches",
        [
            Item(
                "List batches",
                detail="state and counts",
                action=action(ui, "batch", "list"),
            ),
            Item("Show a batch", children=_batch_items(ui, "show")),
            Item(
                "Validate a file", detail="offline checks", action=lambda: _validate(ui)
            ),
            Item(
                "Preview a file", detail="per-message plan", action=lambda: _preview(ui)
            ),
            Item("Submit a file", detail="write a batch", action=lambda: _submit(ui)),
            Item("Approve a batch", children=_approve_items(ui)),
            Item("Cancel a batch", children=_cancel_items(ui)),
            Item(
                "Follow up", detail="add a follow-up step", action=lambda: _followup(ui)
            ),
            Item(
                "Suppressions",
                detail="who will be skipped",
                children=_suppression_items(ui),
            ),
            Item("Quit", action=quit_menu),
        ],
    )


def _suppression_items(ui: Ui) -> list[Item]:
    found = rows(ui, "/api/batches")
    if found is None:
        return need_daemon(ui)
    return [
        Item(
            row["name"],
            detail=row["state"],
            action=action(ui, "batch", "suppression", row["id"]),
        )
        for row in found
    ]


def _job_items(ui: Ui, verb: str) -> list[Item]:
    found = rows(ui, "/api/jobs")
    if found is None:
        return need_daemon(ui)
    if not found:
        return [Item("No jobs yet", detail="submit a campaign first")]
    return [
        Item(
            row["recipient"],
            detail=f"{row['state']}  {row['id']}",
            action=action(ui, "job", verb, row["id"]),
        )
        for row in found
    ]


def _create_job(ui: Ui) -> None:
    found = rows(ui, "/api/accounts")
    if found is None:
        return
    if not found:
        if prompts.confirm(
            "No account is configured. Add one now?", ui=ui, default=True
        ):
            run_args(ui, "account", "add")
        return
    account = prompts.choose(
        "Sending account",
        [prompts.Option(row["address"], row["id"], row["status"]) for row in found],
        ui=ui,
        back=False,
    )
    to = prompts.ask("Recipient", ui=ui, field="--to")
    subject = prompts.ask("Subject", ui=ui, field="--subject")
    text = prompts.ask("Body (one line, blank to open $EDITOR)", ui=ui, required=False)
    argv = [
        "job",
        "create",
        "--account",
        str(account),
        "--to",
        to,
        "--subject",
        subject,
    ]
    if text:
        argv.extend(["--text", text])
        run_args(ui, *argv)
        return
    editor = prompts.ask("Open the editor now?", ui=ui, default="yes", required=False)
    if editor.strip().lower() in {"y", "yes"}:
        body = prompts.open_editor(subject, ui=ui)
        argv.extend(["--text", body.strip()])
    run_args(ui, *argv)


def job_menu(ui: Ui) -> None:
    run(
        ui,
        "Jobs",
        [
            Item(
                "List jobs",
                detail="queue and history",
                action=action(ui, "job", "list"),
            ),
            Item("Show a job", children=_job_items(ui, "show")),
            Item("Send a job now", children=_job_items(ui, "send")),
            Item(
                "Create a job",
                detail="one message by hand",
                action=lambda: _create_job(ui),
            ),
            Item("Quit", action=quit_menu),
        ],
    )


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
