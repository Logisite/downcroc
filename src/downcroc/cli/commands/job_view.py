from __future__ import annotations

from downcroc.cli.commands import when
from downcroc.cli.logs_addresses import AddressBook
from downcroc.cli.output import record, table
from downcroc.cli.ui.session import Ui


def sender_label(job: dict, book: AddressBook | None = None) -> str:
    if job.get("sender_policy") == "auto" or job.get("account_id") is None:
        return "auto"
    account = job["account_id"]
    if book is not None:
        account = book.address(str(account)) or account
    return f"pinned {account}"


def _state(item: dict) -> str:
    return f"{item['state']} (paused)" if item.get("paused_at") else item["state"]


def job_list(rows: list[dict], book: AddressBook | None = None) -> None:
    table(
        ["id", "recipient", "state", "sender", "attempts", "eta", "subject", "sent"],
        [
            [
                item["id"],
                item["recipient"],
                _state(item),
                sender_label(item, book),
                item["attempts"],
                when.cell(item.get("eta")),
                item["subject"],
                item["sent_at"],
            ]
            for item in rows
        ],
    )


def job_show(job: dict, ui: Ui, sender: str | None = None) -> None:
    error = job.get("last_error") or {}
    record(
        {
            "id": job["id"],
            "batch": job["batch_id"],
            "sender": sender or sender_label(job),
            "recipient": job["recipient"],
            "name": job["recipient_name"],
            "subject": job["subject"],
            "state": _state(job),
            "attempts": job["attempts"],
            "message_id": job["message_id"],
            "thread_root": job["thread_root_job_id"],
            "next_attempt_at": job["next_attempt_at"],
            "sent_at": job["sent_at"],
            "error": error.get("code"),
            "error_message": error.get("message"),
        }
    )
    when.show_eta(job.get("eta"), ui)


def attempts_table(rows: list[dict]) -> None:
    table(
        ["started", "transport", "binding", "account", "outcome", "accepted", "error"],
        [
            [
                row["started_at"],
                row["transport"],
                row["binding_id"] or "-",
                row["account_id"] or "-",
                row["outcome"],
                "-" if row["accepted"] is None else str(row["accepted"]).lower(),
                row["error_code"] or "",
            ]
            for row in rows
        ],
    )
