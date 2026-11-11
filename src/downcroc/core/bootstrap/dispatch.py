from __future__ import annotations

from downcroc.core.bootstrap.foundation import Foundation
from downcroc.core.dispatch import Dispatcher, FailureService
from downcroc.core.followups import FollowUpService
from downcroc.core.outbound import OutboundService
from downcroc.core.transports import TransportService


def build_dispatcher(
    foundation: Foundation,
    transports: TransportService,
    failures: FailureService,
    followups: FollowUpService,
    outbound: OutboundService,
) -> Dispatcher:
    return Dispatcher(
        foundation.settings,
        foundation.jobs,
        foundation.accounts,
        transports,
        foundation.batches,
        foundation.quota,
        foundation.runtime,
        failures,
        followups,
        outbound,
        foundation.vault,
        foundation.policy,
        foundation.bus,
        foundation.log,
        foundation.connectivity_state,
    )
