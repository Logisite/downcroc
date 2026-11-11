from __future__ import annotations

from downcroc.core.bootstrap.foundation import Foundation
from downcroc.core.inbound import InboundService


def build_inbound(foundation: Foundation) -> InboundService:
    settings = foundation.settings
    return InboundService(
        foundation.accounts,
        foundation.messages,
        foundation.stats,
        foundation.providers,
        foundation.vault,
        foundation.tokens,
        foundation.clients,
        foundation.content,
        foundation.bus,
        foundation.log,
        settings.inbound,
        settings.connect,
        settings.outbound.api_timeout_s,
        foundation.runtime,
        foundation.connectivity_state,
    )
