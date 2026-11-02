from __future__ import annotations

from downcroc.cli.ui import prompts
from downcroc.cli.ui.data import action, need_daemon, rows
from downcroc.cli.ui.menu import Item, quit_menu, run, run_args
from downcroc.cli.ui.menus_holds import batch_hold_items, job_hold_items
from downcroc.cli.ui.menus_more import (  # noqa: F401 - re-exported for open_menu
    backup_menu,
    failed_menu,
    mail_menu,
    template_menu,
)
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


def _submenu(ui: Ui, title: str, items: list[Item]) -> None:
    run(ui, title, items, breadcrumb="Work")


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
            Item(
                "Show a batch",
                action=lambda: _submenu(ui, "Show a batch", _batch_items(ui, "show")),
            ),
            Item(
                "Validate a file", detail="offline checks", action=lambda: _validate(ui)
            ),
            Item(
                "Preview a file", detail="per-message plan", action=lambda: _preview(ui)
            ),
            Item("Submit a file", detail="write a batch", action=lambda: _submit(ui)),
            Item(
                "Approve a batch",
                action=lambda: _submenu(ui, "Approve a batch", _approve_items(ui)),
            ),
            Item(
                "Cancel a batch",
                action=lambda: _submenu(ui, "Cancel a batch", _cancel_items(ui)),
            ),
            Item(
                "Pause a batch",
                action=lambda: _submenu(
                    ui, "Pause a batch", batch_hold_items(ui, "pause")
                ),
            ),
            Item(
                "Resume the batch",
                action=lambda: _submenu(
                    ui, "Resume a batch", batch_hold_items(ui, "resume")
                ),
            ),
            Item(
                "Follow up", detail="add a follow-up step", action=lambda: _followup(ui)
            ),
            Item(
                "Suppressions",
                detail="who will be skipped",
                action=lambda: _submenu(ui, "Suppressions", _suppression_items(ui)),
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


def _sender_label(row: dict) -> str:
    if row.get("sender_policy") == "auto" or row.get("account_id") is None:
        return "auto"
    return f"pinned {row['account_id']}"


def _sender_items(ui: Ui) -> list[Item]:
    found = rows(ui, "/api/jobs")
    if found is None:
        return need_daemon(ui)
    if not found:
        return [Item("No jobs yet", detail="submit a campaign first")]
    return [
        Item(
            row["recipient"],
            detail=f"{_sender_label(row)}  {row['state']}  {row['id']}",
            action=lambda row=row: _sender_card(ui, row),
        )
        for row in found
    ]


def _sender_card(ui: Ui, row: dict) -> None:
    print(f"  recipient {row['recipient']}")
    print(f"  sender    {_sender_label(row)}")
    choice = prompts.choose(
        f"Sender for {row['id']}",
        [
            prompts.Option("Pin to an account", "pin", "one mailbox, chosen now"),
            prompts.Option("Route at send time", "unpin", "any eligible mailbox"),
            prompts.Option("Show attempts", "attempts", "what carried it"),
        ],
        ui=ui,
        back=True,
    )
    if choice is None:
        return
    if choice == "attempts":
        run_args(ui, "job", "attempts", row["id"])
        return
    if choice == "unpin":
        if row.get("sender_policy") == "auto":
            print("  this job already routes at send time")
            return
        if prompts.confirm("Route this job at send time?", ui=ui, default=True):
            run_args(ui, "job", "reassign", "--job", row["id"], "--unpin", "--yes")
        return
    accounts = rows(ui, "/api/accounts")
    if not accounts:
        print("  no account can take the pin")
        return
    target = prompts.choose(
        "Pin to account",
        [
            prompts.Option(account["address"], account["id"], account["status"])
            for account in accounts
        ],
        ui=ui,
        back=True,
    )
    if target is None:
        return
    if prompts.confirm(f"Pin this job to {target}?", ui=ui, default=True):
        run_args(
            ui,
            "job",
            "reassign",
            "--job",
            row["id"],
            "--to",
            str(target),
            "--pin",
            "--yes",
        )


def _attempt_items(ui: Ui) -> list[Item]:
    found = rows(ui, "/api/jobs")
    if found is None:
        return need_daemon(ui)
    if not found:
        return [Item("No jobs yet", detail="submit a campaign first")]
    return [
        Item(
            row["recipient"],
            detail=f"{row['state']}  {row['id']}",
            action=action(ui, "job", "attempts", row["id"]),
        )
        for row in found
    ]


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
            Item(
                "Show a job",
                action=lambda: _submenu(ui, "Show a job", _job_items(ui, "show")),
            ),
            Item(
                "Send a job now",
                action=lambda: _submenu(ui, "Send a job now", _job_items(ui, "send")),
            ),
            Item(
                "Pause a job",
                action=lambda: _submenu(ui, "Pause a job", job_hold_items(ui, "pause")),
            ),
            Item(
                "Resume a job",
                action=lambda: _submenu(
                    ui, "Resume a job", job_hold_items(ui, "resume")
                ),
            ),
            Item(
                "Reassign sender",
                detail="pin or route at send time",
                action=lambda: _submenu(ui, "Reassign sender", _sender_items(ui)),
            ),
            Item(
                "Show attempts",
                action=lambda: _submenu(ui, "Show attempts", _attempt_items(ui)),
            ),
            Item(
                "Create a job",
                detail="one message by hand",
                action=lambda: _create_job(ui),
            ),
            Item("Quit", action=quit_menu),
        ],
    )
