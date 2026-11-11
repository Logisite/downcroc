from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy import Engine
    from sqlalchemy.orm import Session, sessionmaker

    from downcroc.backup import BackupService, RestoreService
    from downcroc.core.accounts import AccountsService
    from downcroc.core.accounts.preflight import AuthPreflight
    from downcroc.core.batches import BatchesService
    from downcroc.core.capacity import CapacityService
    from downcroc.core.config_service import ConfigService
    from downcroc.core.connectivity import ConnectivityMonitor, ConnectivityState
    from downcroc.core.dispatch import Dispatcher, FailureService
    from downcroc.core.doctor import DoctorService
    from downcroc.core.events import EventBus
    from downcroc.core.followups import FollowUpService
    from downcroc.core.holds import HoldsService
    from downcroc.core.inbound import InboundService
    from downcroc.core.oauth_clients import OAuthClientService
    from downcroc.core.outbound import OutboundService
    from downcroc.core.policy import PolicyResolver
    from downcroc.core.policy.service import PolicyService
    from downcroc.core.portability import PortabilityService
    from downcroc.core.retention import RetentionService
    from downcroc.core.stats import StatsService
    from downcroc.core.transports import TransportService
    from downcroc.core.vault import VaultService
    from downcroc.core.vault.credentials import CredentialPresence
    from downcroc.core.vault.prune import VaultMaintenance
    from downcroc.providers.registry import ProviderRegistry
    from downcroc.store.content import ContentStore
    from downcroc.store.repositories.events import EventRepo
    from downcroc.store.repositories.messages import MessageRepo
    from downcroc.store.repositories.send_attempts import SendAttemptRepo


@dataclass
class Services:
    engine: Engine
    sessions: sessionmaker[Session]
    events: EventRepo
    bus: EventBus
    accounts: AccountsService
    vault: VaultService
    vault_maintenance: VaultMaintenance
    presence: CredentialPresence
    auth_preflight: AuthPreflight
    providers: ProviderRegistry
    messages: MessageRepo
    content: ContentStore
    policy: PolicyResolver
    policy_overrides: PolicyService
    inbound: InboundService
    outbound: OutboundService
    batches: BatchesService
    capacity: CapacityService
    holds: HoldsService
    doctor: DoctorService
    portability: PortabilityService
    followups: FollowUpService
    stats: StatsService
    retention: RetentionService
    failures: FailureService
    send_attempts: SendAttemptRepo
    transports: TransportService
    oauth_clients: OAuthClientService
    dispatcher: Dispatcher
    backup: BackupService
    restore: RestoreService
    config: ConfigService
    connectivity_state: ConnectivityState
    connectivity: ConnectivityMonitor

    def close(self) -> None:
        self.connectivity.stop()
        self.inbound.close()
        self.engine.dispose()
