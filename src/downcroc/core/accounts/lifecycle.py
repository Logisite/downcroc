from __future__ import annotations

from downcroc.core.accounts.watcher import WatcherControl
from downcroc.core.events import EventBus
from downcroc.core.vault import VaultService
from downcroc.domain.accounts import Account, AccountStatus
from downcroc.domain.errors import VaultLocked
from downcroc.domain.jobs import JobState, SenderPolicy
from downcroc.runtime.clock import utc_now
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.repositories.accounts import AccountRepo
from downcroc.store.repositories.jobs import JobRepo


class AccountLifecycle:
    """Archive and unarchive as state transitions, not flag writes."""

    def __init__(
        self,
        accounts: AccountRepo,
        jobs: JobRepo,
        vault: VaultService,
        watcher: WatcherControl,
        bus: EventBus,
        log: EventLogger,
    ) -> None:
        self._accounts = accounts
        self._jobs = jobs
        self._vault = vault
        self._watcher = watcher
        self._bus = bus
        self._log = log

    def archive(self, account_id: str) -> Account:
        account = self._accounts.get(account_id)
        if account.archived_at is not None:
            return account
        queued, pinned = self._stranded(account.id)
        updated = self._accounts.archive(account.id, utc_now())
        self._watcher.account_changed(account.id, False)
        self._publish_watcher(account.id, False)
        present = self._present(updated)
        self._bus.publish(
            "account.archived",
            {
                "id": account.id,
                "watcher_enabled": updated.watcher_enabled,
                "status": updated.status.value,
                "credential_present": present,
                "queued_jobs": queued,
                "pinned_jobs": pinned,
            },
        )
        self._log.info(
            "account.archived",
            account=account.id,
            watcher_enabled=updated.watcher_enabled,
            status=updated.status.value,
            credential_present=present,
            queued_jobs=queued,
            pinned_jobs=pinned,
        )
        return updated

    def unarchive(self, account_id: str) -> Account:
        account = self._accounts.get(account_id)
        if account.archived_at is None:
            return account
        updated = self._accounts.unarchive(account.id)
        present = self._present(updated)
        if present:
            updated = self._accounts.set_watcher_enabled(account.id, True)
            self._watcher.account_changed(account.id, True)
            self._publish_watcher(account.id, True)
        else:
            updated = self._accounts.set_watcher_enabled(account.id, False)
            self._watcher.account_changed(account.id, False)
            updated = self._needs_reauth(updated, "credential_missing")
            self._publish_watcher(account.id, False)
        self._bus.publish(
            "account.unarchived",
            {
                "id": account.id,
                "watcher_enabled": updated.watcher_enabled,
                "status": updated.status.value,
                "credential_present": present,
            },
        )
        self._log.info(
            "account.unarchived",
            account=account.id,
            watcher_enabled=updated.watcher_enabled,
            status=updated.status.value,
            credential_present=present,
        )
        return updated

    def _stranded(self, account_id: str) -> tuple[int, int]:
        queued = self._jobs.count(account_id=account_id, state=JobState.QUEUED.value)
        pinned = sum(
            1
            for job in self._jobs.list(account_id=account_id, limit=10_000)
            if job.sender_policy is SenderPolicy.PINNED
            and job.state
            in (JobState.QUEUED, JobState.RETRY_WAIT, JobState.AWAITING_APPROVAL)
        )
        return queued, pinned

    def _present(self, account: Account) -> bool:
        if account.credential_key is None:
            return False
        try:
            return self._vault.has_secret(account.credential_key)
        except VaultLocked:
            return False

    def _needs_reauth(self, account: Account, reason: str) -> Account:
        if (
            account.status is AccountStatus.NEEDS_REAUTH
            and account.last_error == reason
        ):
            return account
        updated = self._accounts.mark_needs_reauth(account.id, reason)
        self._bus.publish(
            "account.needs_reauth",
            {"id": updated.id, "reason": reason},
        )
        self._log.warning(
            "account.needs_reauth",
            account=updated.id,
            reason=reason,
        )
        return updated

    def _publish_watcher(self, account_id: str, enabled: bool) -> None:
        self._bus.publish(
            "account.watcher",
            {"id": account_id, "enabled": enabled},
        )
        self._log.info(
            "account.watcher",
            account=account_id,
            enabled=enabled,
        )
