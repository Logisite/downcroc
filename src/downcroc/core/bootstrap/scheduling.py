from __future__ import annotations

from downcroc.core.batches import BatchesService
from downcroc.core.bootstrap.foundation import Foundation
from downcroc.core.capacity import CapacityService
from downcroc.core.holds import HoldsService
from downcroc.core.outbound import OutboundService
from downcroc.core.transports import TransportService


def build_capacity(
    foundation: Foundation, transports: TransportService
) -> CapacityService:
    return CapacityService(
        foundation.settings,
        foundation.accounts,
        transports,
        foundation.policy,
        foundation.quota,
        foundation.jobs,
        foundation.batches,
        foundation.runtime,
    )


def build_holds(
    foundation: Foundation,
    transports: TransportService,
    capacity: CapacityService,
) -> HoldsService:
    return HoldsService(
        foundation.settings,
        foundation.runtime,
        foundation.accounts,
        foundation.batches,
        foundation.jobs,
        capacity,
        transports,
        foundation.bus,
        foundation.log,
    )


def build_batches(
    foundation: Foundation,
    outbound: OutboundService,
    capacity: CapacityService,
) -> BatchesService:
    return BatchesService(
        foundation.settings,
        foundation.paths,
        foundation.batches,
        foundation.jobs,
        foundation.accounts,
        foundation.messages,
        foundation.content,
        outbound,
        foundation.stats,
        foundation.policy,
        foundation.bus,
        foundation.log,
        capacity,
    )
