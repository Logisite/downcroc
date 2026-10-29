from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FailedJob:
    job_id: str
    batch_id: str
    account_id: str | None
    recipient: str
    code: str
    message: str
    retryable: bool | None
    attempts: int
    failed_at: str
