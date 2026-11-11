from __future__ import annotations

from downcroc.core.accounts import AccountEligibility
from downcroc.core.bootstrap.accounts import build_accounts
from downcroc.core.bootstrap.dispatch import build_dispatcher
from downcroc.core.bootstrap.failures import build_failures
from downcroc.core.bootstrap.foundation import open_foundation
from downcroc.core.bootstrap.inbound import build_inbound
from downcroc.core.bootstrap.operations import build_operations
from downcroc.core.bootstrap.outbound import build_outbound
from downcroc.core.bootstrap.scheduling import (
    build_batches,
    build_capacity,
    build_holds,
)
from downcroc.core.bootstrap.services import Services
from downcroc.core.bootstrap.support import build_support
from downcroc.core.bootstrap.transports import build_transports
from downcroc.runtime.config.schema import Settings
from downcroc.runtime.logging.setup import EventLogger
from downcroc.runtime.paths import Paths


def build(settings: Settings, paths: Paths, log: EventLogger) -> Services:
    foundation = open_foundation(settings, paths, log)
    eligibility = AccountEligibility(foundation.policy, foundation.presence)
    inbound = build_inbound(foundation)
    transports, credentials = build_transports(foundation, eligibility)
    accounts, vault_maintenance = build_accounts(foundation, inbound, transports)
    outbound = build_outbound(foundation, transports, eligibility)
    inbound.open()
    capacity = build_capacity(foundation, transports)
    holds = build_holds(foundation, transports, capacity)
    batches = build_batches(foundation, outbound, capacity, eligibility)
    failures = build_failures(foundation)
    operations = build_operations(
        foundation,
        transports,
        credentials,
        capacity,
        holds,
        inbound,
    )
    dispatcher = build_dispatcher(
        foundation,
        transports,
        failures,
        operations.followups,
        outbound,
        eligibility,
    )
    support = build_support(foundation, operations.followups)
    return Services(
        engine=foundation.engine,
        sessions=foundation.sessions,
        events=foundation.events,
        bus=foundation.bus,
        accounts=accounts,
        vault=foundation.vault,
        vault_maintenance=vault_maintenance,
        presence=foundation.presence,
        providers=foundation.providers,
        messages=foundation.messages,
        content=foundation.content,
        policy=foundation.policy,
        policy_overrides=foundation.policy_service,
        inbound=inbound,
        outbound=outbound,
        batches=batches,
        capacity=capacity,
        holds=holds,
        doctor=operations.doctor,
        portability=operations.portability,
        followups=operations.followups,
        stats=foundation.stats,
        retention=operations.retention,
        failures=failures,
        send_attempts=foundation.send_attempts,
        transports=transports,
        oauth_clients=foundation.clients,
        dispatcher=dispatcher,
        backup=support.backup,
        restore=support.restore,
        config=support.config,
        connectivity_state=foundation.connectivity_state,
        connectivity=support.connectivity,
    )
