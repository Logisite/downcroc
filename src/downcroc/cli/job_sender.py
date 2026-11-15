from __future__ import annotations

from typing import Any

from downcroc.cli.client import get
from downcroc.cli.logs_addresses import AddressBook

SENT_OUTCOMES = {"sent", "sent_unconfirmed"}


def resolve_sender(client: Any, job: dict) -> str | None:
    """Return the account that actually sent the job, from the live record."""
    account = job.get("account_id")
    if account:
        return str(account)
    for attempt in get(client, f"/api/jobs/{job['id']}/attempts"):
        if (
            attempt.get("outcome") in SENT_OUTCOMES
            and attempt.get("accepted")
            and attempt.get("account_id")
        ):
            return str(attempt["account_id"])
    return None


def sender_text(
    client: Any, job: dict, book: AddressBook | None, addresses: bool
) -> str | None:
    """Build the sender display, or None to keep the default label."""
    account = job.get("account_id")
    if account:
        if not addresses:
            return None
        prefix = "pinned" if job.get("sender_policy") == "pinned" else "auto"
        label = book.address(str(account)) if book else None
        return f"{prefix} {label or account}"
    resolved = resolve_sender(client, job)
    if resolved is None:
        return "auto (not sent yet)" if addresses else None
    label = (book.address(resolved) or resolved) if addresses else resolved
    return f"auto (sent from {label})"
