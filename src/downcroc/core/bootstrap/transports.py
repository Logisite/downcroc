from __future__ import annotations

from downcroc.core.bootstrap.foundation import Foundation
from downcroc.core.credentials import CredentialResolver
from downcroc.core.transports import TransportService


def build_transports(
    foundation: Foundation,
) -> tuple[TransportService, CredentialResolver]:
    credentials = CredentialResolver(
        foundation.accounts,
        foundation.vault,
        foundation.tokens,
        foundation.clients,
    )
    transports = TransportService(
        foundation.transports,
        foundation.accounts,
        foundation.providers,
        credentials,
        foundation.clients,
        foundation.bus,
        foundation.log,
        foundation.events,
        foundation.settings.outbound,
        foundation.settings.dispatch,
        foundation.policy,
        foundation.quota,
    )
    for account in foundation.accounts.list(include_archived=True):
        transports.ensure_defaults(account)
    return transports, credentials
