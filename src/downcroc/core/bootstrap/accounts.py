from __future__ import annotations

from downcroc.core.accounts import AccountsService
from downcroc.core.bootstrap.foundation import Foundation
from downcroc.core.inbound import InboundService
from downcroc.core.transports import TransportService
from downcroc.core.vault.prune import VaultMaintenance


def build_accounts(
    foundation: Foundation,
    inbound: InboundService,
    transports: TransportService,
) -> tuple[AccountsService, VaultMaintenance]:
    accounts = AccountsService(
        foundation.accounts,
        foundation.bus,
        foundation.log,
        foundation.providers,
        foundation.vault,
        foundation.tokens,
        foundation.attempts,
        foundation.settings.connect,
        inbound,
        foundation.content,
        foundation.stats,
        transports,
        foundation.clients,
    )
    maintenance = VaultMaintenance(
        foundation.vault,
        accounts,
        foundation.presence,
        foundation.log,
    )
    return accounts, maintenance
