from __future__ import annotations

from dataclasses import dataclass

from downcroc.runtime.clock import parse_utc

MOVABLE = ("queued", "awaiting_approval", "retry_wait")
HISTORY = ("sent", "sent_unconfirmed", "cancelled")
TERMINAL = ("sent", "sent_unconfirmed", "cancelled", "failed")


@dataclass(frozen=True)
class Selection:
    job_ids: list[str] | None = None
    batch_ids: list[str] | None = None
    account_id: str | None = None
    states: list[str] | None = None
    created_since: str | None = None
    created_until: str | None = None
    sent_since: str | None = None
    sent_until: str | None = None

    def as_filters(self) -> dict[str, object]:
        return {
            "job_ids": self.job_ids,
            "batch_ids": self.batch_ids,
            "account_id": self.account_id,
            "states": self.states,
            "created_since": moment(self.created_since),
            "created_until": moment(self.created_until),
            "sent_since": moment(self.sent_since),
            "sent_until": moment(self.sent_until),
        }


def moment(value: str | None) -> str | None:
    if value is None:
        return None
    return parse_utc(value).isoformat(timespec="milliseconds").replace("+00:00", "Z")
