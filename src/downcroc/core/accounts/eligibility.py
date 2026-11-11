from __future__ import annotations

from downcroc.core.policy import PolicyResolver
from downcroc.core.vault.credentials import CredentialPresence
from downcroc.domain.accounts import Account, AccountStatus


class AccountEligibility:
    """One eligibility rule for routing, dispatch, seats, and manual sends."""

    def __init__(self, policy: PolicyResolver, presence: CredentialPresence) -> None:
        self._policy = policy
        self._presence = presence

    def routable(self, account: Account) -> bool:
        return (
            account.archived_at is None
            and account.status is AccountStatus.CONNECTED
            and self._policy.effective(account).enabled
            and self._presence.present(account)
        )

    def sendable(self, account: Account) -> bool:
        return self.routable(account) and account.paused_at is None

    def credential_present(self, account: Account) -> bool:
        return self._presence.present(account)
