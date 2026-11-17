from __future__ import annotations

from pydantic import BaseModel

from downcroc.core.backfill import (
    AccountBackfill,
    BackfillStatus,
    HoleExplanation,
)


class AccountBackfillOut(BaseModel):
    account_id: str
    address: str | None
    status: str
    due: int
    waiting: int
    missing: int
    unresolved: int
    open: int
    total: int
    next_due_at: str | None
    blocked_reason: str | None

    @classmethod
    def of(cls, row: AccountBackfill) -> AccountBackfillOut:
        return cls(
            account_id=row.account_id,
            address=row.address,
            status=row.status,
            due=row.due,
            waiting=row.waiting,
            missing=row.missing,
            unresolved=row.unresolved,
            open=row.open,
            total=row.total,
            next_due_at=row.next_due_at,
            blocked_reason=row.blocked_reason,
        )


class BackfillStatusOut(BaseModel):
    checked_at: str
    due: int
    waiting: int
    missing: int
    unresolved: int
    open: int
    total: int
    next_due_at: str | None
    accounts: list[AccountBackfillOut]
    unknown_accounts: list[str]

    @classmethod
    def of(cls, status: BackfillStatus) -> BackfillStatusOut:
        return cls(
            checked_at=status.checked_at,
            due=status.due,
            waiting=status.waiting,
            missing=status.missing,
            unresolved=status.unresolved,
            open=status.open,
            total=status.total,
            next_due_at=status.next_due_at,
            accounts=[AccountBackfillOut.of(row) for row in status.accounts],
            unknown_accounts=list(status.unknown_accounts),
        )


class HoleOut(BaseModel):
    attempt_id: str
    job_id: str
    account_id: str | None
    address: str | None
    account_status: str | None
    message_id: str | None
    outcome: str
    started_at: str
    finished_at: str | None
    provider_message_id: str | None
    provider_thread_id: str | None
    thread_status: str | None
    first_miss_at: str | None
    missing_at: str | None
    last_checked_at: str | None
    next_check_at: str | None
    check_count: int
    last_result: str | None
    last_scope: str | None
    last_error: str | None
    blocked_reason: str | None

    @classmethod
    def of(cls, found: HoleExplanation) -> HoleOut:
        row = found.detail
        return cls(
            attempt_id=row.attempt_id,
            job_id=row.job_id,
            account_id=row.account_id,
            address=found.address,
            account_status=found.account_status,
            message_id=row.message_id,
            outcome=row.outcome,
            started_at=row.started_at,
            finished_at=row.finished_at,
            provider_message_id=row.provider_message_id,
            provider_thread_id=row.provider_thread_id,
            thread_status=row.thread_status,
            first_miss_at=row.first_miss_at,
            missing_at=row.missing_at,
            last_checked_at=row.last_checked_at,
            next_check_at=row.next_check_at,
            check_count=row.check_count,
            last_result=row.last_result,
            last_scope=row.last_scope,
            last_error=row.last_error,
            blocked_reason=found.blocked_reason,
        )
