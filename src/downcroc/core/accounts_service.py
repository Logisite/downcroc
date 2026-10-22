from __future__ import annotations

from downcroc.core.events import EventBus
from downcroc.domain.accounts import Account, AccountStatus, SendPolicy
from downcroc.domain.validators import validate_account
from downcroc.runtime.clock import utc_now
from downcroc.runtime.ids import new_id
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.repositories.accounts import AccountRepo


class AccountsService:
    def __init__(
        self,
        accounts: AccountRepo,
        bus: EventBus,
        log: EventLogger,
        policy: SendPolicy,
    ) -> None:
        self._accounts = accounts
        self._bus = bus
        self._log = log
        self._policy = policy

    def create(self, provider: str, address: str, label: str) -> Account:
        provider, address, label = validate_account(provider, address, label)
        account = Account(
            id=new_id("acct"),
            provider=provider,
            address=address,
            label=label,
            status=AccountStatus.PENDING,
            credential_present=False,
            created_at=utc_now(),
            last_verified_at=None,
            policy=self._policy,
        )
        self._accounts.create(account)
        self._bus.publish("account.added", {"id": account.id})
        self._log.info("account.created", account=account.id, provider=provider)
        return account

    def list(self) -> list[Account]:
        return self._accounts.list()

    def get(self, account_id: str) -> Account:
        return self._accounts.get(account_id)

    def delete(self, account_id: str) -> None:
        self._accounts.delete(account_id)
        self._bus.publish("account.removed", {"id": account_id})
        self._log.info("account.deleted", account=account_id)
