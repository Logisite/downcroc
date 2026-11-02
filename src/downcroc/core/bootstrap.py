from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from downcroc.backup import BackupService, RestoreService
from downcroc.core.accounts_service import AccountsService
from downcroc.core.batches import BatchesService
from downcroc.core.capacity import CapacityService
from downcroc.core.config_service import ConfigService
from downcroc.core.credentials import CredentialResolver
from downcroc.core.dispatch import Dispatcher, FailureLog, FailureService
from downcroc.core.doctor import DoctorService
from downcroc.core.events import EventBus
from downcroc.core.followups import FollowUpService
from downcroc.core.inbound import InboundService
from downcroc.core.oauth_clients import OAuthClientService
from downcroc.core.outbound import OutboundService
from downcroc.core.policy import PolicyResolver
from downcroc.core.policy_service import PolicyService
from downcroc.core.portability import PortabilityService
from downcroc.core.retention import RetentionService
from downcroc.core.stats import StatsService
from downcroc.core.transport_doctor import TransportChecks
from downcroc.core.transports import TransportService
from downcroc.core.vault_service import VaultService
from downcroc.providers.registry import ProviderRegistry
from downcroc.providers.token import TokenManager
from downcroc.runtime.config.schema import Settings
from downcroc.runtime.logging.setup import EventLogger
from downcroc.runtime.paths import Paths
from downcroc.store.content import ContentStore
from downcroc.store.db.engine import open_database, sessions_for
from downcroc.store.db.migrate import run_migrations
from downcroc.store.repositories.accounts import AccountRepo
from downcroc.store.repositories.activity import ActivityRepo
from downcroc.store.repositories.attempts import AttemptRepo
from downcroc.store.repositories.batch_counters import BatchCounterRepo
from downcroc.store.repositories.batches import BatchRepo
from downcroc.store.repositories.events import EventRepo
from downcroc.store.repositories.failures import FailureRepo
from downcroc.store.repositories.jobs import JobRepo
from downcroc.store.repositories.messages import MessageRepo
from downcroc.store.repositories.oauth_clients import OAuthClientRepo
from downcroc.store.repositories.policy import PolicyRepo
from downcroc.store.repositories.quota import QuotaRepo
from downcroc.store.repositories.runtime_state import RuntimeStateRepo
from downcroc.store.repositories.send_attempts import SendAttemptRepo
from downcroc.store.repositories.transports import TransportRepo


@dataclass
class Services:
    engine: Engine
    sessions: sessionmaker[Session]
    events: EventRepo
    bus: EventBus
    accounts: AccountsService
    vault: VaultService
    providers: ProviderRegistry
    messages: MessageRepo
    content: ContentStore
    policy: PolicyResolver
    policy_overrides: PolicyService
    inbound: InboundService
    outbound: OutboundService
    batches: BatchesService
    capacity: CapacityService
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

    def close(self) -> None:
        self.inbound.close()
        self.engine.dispose()


def build(settings: Settings, paths: Paths, log: EventLogger) -> Services:
    engine = open_database(paths.data / "downcroc.db")
    run_migrations(engine, log)
    sessions = sessions_for(engine)
    events = EventRepo(sessions, settings.events.ring_size)
    bus = EventBus(events, settings.events.queue_size)
    policy_repo = PolicyRepo(sessions)
    policy = PolicyResolver(settings, policy_repo)
    policy_repo.clear_expired()
    vault = VaultService(paths.data / "vault.enc", settings.vault, bus, log)
    providers = ProviderRegistry.load(paths.config, log)
    attempts = AttemptRepo(sessions)
    attempts.expire_pending("daemon_restart")
    tokens = TokenManager(vault, providers, settings.connect, log)
    account_repo = AccountRepo(sessions)
    policy_service = PolicyService(account_repo, policy_repo, policy, bus, log)
    message_repo = MessageRepo(sessions)
    job_repo = JobRepo(sessions)
    batch_repo = BatchRepo(sessions)
    quota_repo = QuotaRepo(sessions)
    send_attempts = SendAttemptRepo(sessions)
    stale = send_attempts.release_reserved()
    quota_repo.reset_reservations()
    if stale:
        log.info("quota.reservations_reset", count=stale)
    runtime_repo = RuntimeStateRepo(sessions)
    transport_repo = TransportRepo(sessions)
    oauth_client_repo = OAuthClientRepo(sessions)
    activity_repo = ActivityRepo(sessions)
    counter_repo = BatchCounterRepo(sessions)
    content = ContentStore(paths.data / "content")
    stats = StatsService(
        settings,
        activity_repo,
        counter_repo,
        batch_repo,
        job_repo,
        message_repo,
        account_repo,
        quota_repo,
        policy,
        log,
    )
    clients = OAuthClientService(
        oauth_client_repo,
        transport_repo,
        account_repo,
        vault,
        providers,
        bus,
        log,
    )
    inbound = InboundService(
        account_repo,
        message_repo,
        stats,
        providers,
        vault,
        tokens,
        clients,
        content,
        bus,
        log,
        settings.inbound,
        settings.connect,
        settings.outbound.api_timeout_s,
    )
    credentials = CredentialResolver(account_repo, vault, tokens, clients)
    transports = TransportService(
        transport_repo,
        account_repo,
        providers,
        credentials,
        clients,
        bus,
        log,
        events,
        settings.outbound,
        settings.dispatch,
        policy,
        quota_repo,
    )
    for account in account_repo.list(include_archived=True):
        transports.ensure_defaults(account)
    accounts = AccountsService(
        account_repo,
        bus,
        log,
        providers,
        vault,
        tokens,
        attempts,
        settings.connect,
        inbound,
        content,
        stats,
        transports,
        clients,
    )
    outbound = OutboundService(
        job_repo,
        account_repo,
        providers,
        vault,
        tokens,
        clients,
        content,
        stats,
        bus,
        log,
        settings.outbound,
        settings.connect,
        send_attempts,
        transports,
        policy,
        quota_repo,
    )
    inbound.open()
    capacity = CapacityService(
        settings,
        account_repo,
        transports,
        policy,
        quota_repo,
        job_repo,
        batch_repo,
    )
    batches = BatchesService(
        settings,
        paths,
        batch_repo,
        job_repo,
        account_repo,
        message_repo,
        content,
        outbound,
        stats,
        policy,
        bus,
        log,
        capacity,
    )
    transport_checks = TransportChecks(
        settings,
        clients,
        vault,
        providers,
        credentials,
    )
    doctor = DoctorService(
        settings,
        account_repo,
        transports,
        clients,
        capacity,
        inbound,
        transport_checks,
    )
    portability = PortabilityService(
        job_repo,
        batch_repo,
        account_repo,
        counter_repo,
        content,
        stats,
        bus,
        log,
    )
    followups = FollowUpService(
        settings,
        paths,
        batch_repo,
        job_repo,
        account_repo,
        message_repo,
        content,
        inbound,
        stats,
        bus,
        log,
    )
    failure_repo = FailureRepo(sessions)
    failures = FailureService(
        failure_repo,
        FailureLog(paths.data / "failed.jsonl"),
        job_repo,
        batch_repo,
        stats,
        bus,
        log,
    )
    retention = RetentionService(
        settings.retention,
        job_repo,
        message_repo,
        activity_repo,
        content,
        log,
    )
    dispatcher = Dispatcher(
        settings,
        job_repo,
        account_repo,
        transports,
        batch_repo,
        quota_repo,
        runtime_repo,
        failures,
        followups,
        outbound,
        vault,
        policy,
        bus,
        log,
    )
    backup = BackupService(paths, log)
    restore = RestoreService(paths, log)
    config = ConfigService(paths, settings, log, followups)
    return Services(
        engine=engine,
        sessions=sessions,
        events=events,
        bus=bus,
        accounts=accounts,
        vault=vault,
        providers=providers,
        messages=message_repo,
        content=content,
        policy=policy,
        policy_overrides=policy_service,
        inbound=inbound,
        outbound=outbound,
        batches=batches,
        capacity=capacity,
        doctor=doctor,
        portability=portability,
        followups=followups,
        stats=stats,
        retention=retention,
        failures=failures,
        send_attempts=send_attempts,
        transports=transports,
        oauth_clients=clients,
        dispatcher=dispatcher,
        backup=backup,
        restore=restore,
        config=config,
    )
