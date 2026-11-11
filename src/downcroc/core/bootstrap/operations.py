from __future__ import annotations

from dataclasses import dataclass

from downcroc.core.bootstrap.foundation import Foundation
from downcroc.core.capacity import CapacityService
from downcroc.core.credentials import CredentialResolver
from downcroc.core.doctor import DoctorService
from downcroc.core.followups import FollowUpService
from downcroc.core.holds import HoldsService
from downcroc.core.inbound import InboundService
from downcroc.core.portability import PortabilityService
from downcroc.core.retention import RetentionService
from downcroc.core.transport_doctor import TransportChecks
from downcroc.core.transports import TransportService


@dataclass
class Operations:
    doctor: DoctorService
    portability: PortabilityService
    followups: FollowUpService
    retention: RetentionService


def build_operations(
    foundation: Foundation,
    transports: TransportService,
    credentials: CredentialResolver,
    capacity: CapacityService,
    holds: HoldsService,
    inbound: InboundService,
) -> Operations:
    settings = foundation.settings
    checks = TransportChecks(
        settings,
        foundation.clients,
        foundation.vault,
        foundation.providers,
        credentials,
    )
    doctor = DoctorService(
        settings,
        foundation.accounts,
        transports,
        foundation.clients,
        capacity,
        inbound,
        holds,
        checks,
        foundation.quota,
    )
    portability = PortabilityService(
        foundation.jobs,
        foundation.batches,
        foundation.accounts,
        foundation.counters,
        foundation.content,
        foundation.stats,
        foundation.bus,
        foundation.log,
    )
    followups = FollowUpService(
        settings,
        foundation.paths,
        foundation.batches,
        foundation.jobs,
        foundation.accounts,
        foundation.messages,
        foundation.content,
        inbound,
        foundation.stats,
        foundation.bus,
        foundation.log,
    )
    retention = RetentionService(
        settings.retention,
        foundation.jobs,
        foundation.messages,
        foundation.activity,
        foundation.content,
        foundation.log,
    )
    return Operations(
        doctor=doctor,
        portability=portability,
        followups=followups,
        retention=retention,
    )
