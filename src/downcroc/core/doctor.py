from __future__ import annotations

from downcroc.core.capacity import CapacityService
from downcroc.core.oauth_clients import OAuthClientService
from downcroc.core.transports import TransportService
from downcroc.core.vault_service import VaultService
from downcroc.domain.accounts import Account, AccountStatus
from downcroc.domain.transports import TransportKind
from downcroc.runtime.config.schema import Settings
from downcroc.store.repositories.accounts import AccountRepo


class DoctorService:
    """Read-only diagnostics for bindings, clients, and fleet capacity."""

    def __init__(
        self,
        settings: Settings,
        accounts: AccountRepo,
        transports: TransportService,
        clients: OAuthClientService,
        capacity: CapacityService,
        vault: VaultService,
    ) -> None:
        self._settings = settings
        self._accounts = accounts
        self._transports = transports
        self._clients = clients
        self._capacity = capacity
        self._vault = vault

    def transports(self) -> dict[str, object]:
        rows: list[dict[str, object]] = []
        for account in self._accounts.list():
            for binding in self._transports.list(account.id):
                rows.append(self._binding(account, binding))
        clients = [
            {
                "id": client.id,
                "provider_id": client.provider_id,
                "label": client.label,
                "client_id": client.client_id,
                "project_id": client.project_id,
            }
            for client in self._clients.list()
        ]
        problems = [row for row in rows if row["problem"]]
        return {
            "ok": not problems,
            "bindings": rows,
            "clients": clients,
            "problems": problems,
        }

    def capacity(self) -> dict[str, object]:
        fleet = self._capacity.fleet()
        plan = self._transports.pick_slots()
        smtp_only: list[dict[str, str]] = []
        password_only: list[dict[str, str]] = []
        per_kind = {"smtp": 0, "gmail_api": 0}
        for account in self._accounts.list():
            bindings = self._transports.bindings(account)
            kinds = {binding.kind.value for binding in bindings}
            for kind in kinds:
                per_kind[kind] = per_kind.get(kind, 0) + 1
            if kinds == {TransportKind.SMTP.value}:
                smtp_only.append({"account_id": account.id, "address": account.address})
                if self._transports.is_password(account):
                    password_only.append(
                        {"account_id": account.id, "address": account.address}
                    )
        seats = max(1, self._settings.dispatch.smtp_seats)
        return {
            "ok": seats <= 3,
            "lanes": fleet.api_lanes + (1 if fleet.smtp_seats else 0),
            "api_lanes": fleet.api_lanes,
            "smtp_seats": fleet.smtp_seats,
            "configured_smtp_seats": seats,
            "serial": fleet.api_lanes == 0 and fleet.smtp_seats > 0,
            "parallel_sends": self._settings.dispatch.parallel_sends,
            "api_max_concurrency": self._settings.dispatch.api_max_concurrency,
            "bindings_per_kind": per_kind,
            "smtp_active": list(plan.active),
            "smtp_queue": list(plan.queue),
            "smtp_waiting": list(plan.waiting),
            "pinned_overflow": plan.pinned_overflow,
            "password_accounts": fleet.password_accounts,
            "oauth_accounts": fleet.oauth_accounts,
            "oauth_api_only": fleet.oauth_api_only,
            "password_waiting": fleet.password_waiting,
            "smtp_only": smtp_only,
            "password_only": password_only,
            "warning": self._seat_warning(seats),
            "recommendation": (
                "app-password accounts are SMTP-only and bounded to one seat "
                "each; connect a Gmail account with OAuth to use API lanes"
                if password_only
                else None
            ),
        }

    def _binding(self, account: Account, binding) -> dict[str, object]:
        problem = None
        if binding.kind is TransportKind.GMAIL_API and binding.oauth_client_id is None:
            problem = "missing_oauth_client"
        elif binding.kind is TransportKind.GMAIL_API and not self._client_exists(
            binding.oauth_client_id
        ):
            problem = "oauth_client_missing"
        elif account.status is AccountStatus.NEEDS_REAUTH:
            problem = "needs_reauth"
        elif account.status is AccountStatus.PENDING:
            problem = "account_pending"
        elif account.status is AccountStatus.UNVERIFIED:
            problem = "account_unverified"
        elif account.status is AccountStatus.DISABLED:
            problem = "account_disabled"
        elif not binding.enabled:
            problem = "disabled"
        return {
            "account_id": account.id,
            "address": account.address,
            "binding_id": binding.id,
            "kind": binding.kind.value,
            "health": binding.health.value,
            "enabled": binding.enabled,
            "priority": binding.priority,
            "max_concurrency": binding.max_concurrency,
            "rate_per_min": binding.rate_per_min,
            "oauth_client_id": binding.oauth_client_id,
            "last_error_code": binding.last_error_code,
            "cooldown_until": binding.cooldown_until,
            "problem": problem,
        }

    def _client_exists(self, client_id: str | None) -> bool:
        if client_id is None:
            return False
        try:
            self._clients.get(client_id)
            return True
        except Exception:  # noqa: BLE001 - a missing client is the finding
            return False

    @staticmethod
    def _seat_warning(seats: int) -> str | None:
        if seats <= 1:
            return None
        if seats <= 3:
            return (
                "SMTP seats rotate serially across distinct mailboxes. This is "
                "not parallel sending; use Gmail API lanes for throughput."
            )
        return (
            "SMTP seats above 3 are unsupported-risk. Each extra seat is another "
            "mailbox that Gmail may throttle or suspend, and rotation does not "
            "create parallel capacity."
        )
