from __future__ import annotations

from downcroc.cli.output import record, table


def sender_label(job: dict) -> str:
    if job.get("sender_policy") == "auto" or job.get("account_id") is None:
        return "auto"
    return f"pinned {job['account_id']}"


def job_list(rows: list[dict]) -> None:
    table(
        ["id", "recipient", "state", "sender", "attempts", "subject", "sent"],
        [
            [
                item["id"],
                item["recipient"],
                item["state"],
                sender_label(item),
                item["attempts"],
                item["subject"],
                item["sent_at"],
            ]
            for item in rows
        ],
    )


def job_show(job: dict) -> None:
    error = job.get("last_error") or {}
    record(
        {
            "id": job["id"],
            "batch": job["batch_id"],
            "sender": sender_label(job),
            "recipient": job["recipient"],
            "name": job["recipient_name"],
            "subject": job["subject"],
            "state": job["state"],
            "attempts": job["attempts"],
            "message_id": job["message_id"],
            "thread_root": job["thread_root_job_id"],
            "next_attempt_at": job["next_attempt_at"],
            "sent_at": job["sent_at"],
            "error": error.get("code"),
            "error_message": error.get("message"),
        }
    )


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
