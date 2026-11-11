from __future__ import annotations

from downcroc.core.bootstrap.foundation import Foundation
from downcroc.core.outbound import OutboundService
from downcroc.core.transports import TransportService


def build_outbound(
    foundation: Foundation, transports: TransportService
) -> OutboundService:
    settings = foundation.settings
    return OutboundService(
        foundation.jobs,
        foundation.batches,
        foundation.accounts,
        foundation.providers,
        foundation.vault,
        foundation.tokens,
        foundation.clients,
        foundation.content,
        foundation.stats,
        foundation.bus,
        foundation.log,
        settings.outbound,
        settings.connect,
        foundation.send_attempts,
        transports,
        foundation.policy,
        foundation.quota,
        foundation.connectivity_state,
    )
