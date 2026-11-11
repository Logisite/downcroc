from __future__ import annotations

from dataclasses import dataclass

from downcroc.domain.accounts import AccountStatus
from downcroc.domain.errors import (
    AccountNotFound,
    FollowUpSenderUnavailable,
    FollowUpSenderUnresolved,
)
from downcroc.domain.jobs import Job, SenderPolicy
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.repositories.accounts import AccountRepo
from downcroc.store.repositories.send_attempts import SendAttemptRepo

SENT_OUTCOMES = frozenset({"sent", "sent_unconfirmed"})


@dataclass(frozen=True)
class ResolvedSender:
    address: str
    name: str
    account_id: str
    policy: SenderPolicy


class SenderResolver:
    def __init__(
        self,
        accounts: AccountRepo,
        attempts: SendAttemptRepo,
        log: EventLogger,
    ) -> None:
        self._accounts = accounts
        self._attempts = attempts
        self._log = log

    def resolve(self, parent: Job) -> ResolvedSender:
        account_id = parent.account_id or self._attempt_account(parent)
        account = self._account(parent, account_id)
        unavailable = _unavailable_reason(account)
        if unavailable is not None:
            self._log.warning(
                "followup.sender_unavailable",
                parent=parent.id,
                account=account.id,
                reason=unavailable,
            )
            raise FollowUpSenderUnavailable(
                "the parent sender is not available",
                hint="restore or reconnect the parent account",
                fields={"account": account.id},
            )
        return ResolvedSender(
            address=account.address,
            name=account.label,
            account_id=account.id,
            policy=SenderPolicy.PINNED,
        )

    def _attempt_account(self, parent: Job) -> str:
        attempt = self._attempts.latest_for_job(parent.id)
        if (
            attempt is None
            or attempt.account_id is None
            or attempt.outcome not in SENT_OUTCOMES
            or attempt.accepted is False
            or attempt.finished_at is None
        ):
            self._log.warning(
                "followup.sender_unresolved",
                parent=parent.id,
                reason="missing_accepted_attempt",
                attempt_count=0 if attempt is None else 1,
            )
            raise FollowUpSenderUnresolved(
                "the account that sent the parent cannot be determined",
                hint="send the parent again or pin the parent to an account",
            )
        return attempt.account_id

    def _account(self, parent: Job, account_id: str):
        try:
            return self._accounts.get(account_id)
        except AccountNotFound as error:
            self._log.warning(
                "followup.sender_unavailable",
                parent=parent.id,
                account=account_id,
                reason="missing_account",
            )
            raise FollowUpSenderUnavailable(
                "the parent sender account no longer exists",
                hint="restore the parent account",
            ) from error


def _unavailable_reason(account) -> str | None:
    if account.archived_at is not None:
        return "archived"
    if account.paused_at is not None:
        return "paused"
    if account.status is AccountStatus.DISABLED:
        return "disabled"
    if account.status is AccountStatus.NEEDS_REAUTH:
        return "needs_reauth"
    if account.status is AccountStatus.PENDING:
        return "pending"
    if account.credential_key is None:
        return "credential_missing"
    return None
