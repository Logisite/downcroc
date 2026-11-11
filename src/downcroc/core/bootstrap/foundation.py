from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from downcroc.core.connectivity import ConnectivityState
from downcroc.core.events import EventBus
from downcroc.core.oauth_clients import OAuthClientService
from downcroc.core.outbound.attempts.reconcile import reconcile_interrupted
from downcroc.core.policy import PolicyResolver
from downcroc.core.policy_service import PolicyService
from downcroc.core.stats import StatsService
from downcroc.core.vault import VaultService
from downcroc.core.vault.credentials import CredentialPresence
from downcroc.providers.registry import ProviderRegistry
from downcroc.providers.token import TokenManager
from downcroc.runtime.clock import utc_now
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
from downcroc.store.repositories.jobs import JobRepo
from downcroc.store.repositories.messages import MessageRepo
from downcroc.store.repositories.oauth_clients import OAuthClientRepo
from downcroc.store.repositories.policy import PolicyRepo
from downcroc.store.repositories.quota import QuotaRepo
from downcroc.store.repositories.runtime_state import RuntimeStateRepo
from downcroc.store.repositories.send_attempts import SendAttemptRepo
from downcroc.store.repositories.transports import TransportRepo


@dataclass
class Foundation:
    settings: Settings
    paths: Paths
    log: EventLogger
    engine: Engine
    sessions: sessionmaker[Session]
    events: EventRepo
    bus: EventBus
    connectivity_state: ConnectivityState
    policy: PolicyResolver
    policy_repo: PolicyRepo
    policy_service: PolicyService
    vault: VaultService
    presence: CredentialPresence
    providers: ProviderRegistry
    attempts: AttemptRepo
    tokens: TokenManager
    accounts: AccountRepo
    messages: MessageRepo
    jobs: JobRepo
    batches: BatchRepo
    quota: QuotaRepo
    send_attempts: SendAttemptRepo
    runtime: RuntimeStateRepo
    transports: TransportRepo
    oauth_clients: OAuthClientRepo
    activity: ActivityRepo
    counters: BatchCounterRepo
    content: ContentStore
    stats: StatsService
    clients: OAuthClientService


def open_foundation(settings: Settings, paths: Paths, log: EventLogger) -> Foundation:
    engine = open_database(paths.data / "downcroc.db")
    run_migrations(engine, log)
    sessions = sessions_for(engine)
    events = EventRepo(sessions, settings.events.ring_size)
    bus = EventBus(events, settings.events.queue_size)
    connectivity_state = ConnectivityState()
    policy_repo = PolicyRepo(sessions)
    policy = PolicyResolver(settings, policy_repo)
    policy_repo.clear_expired()
    vault = VaultService(paths.data / "vault.enc", settings.vault, bus, log)
    presence = CredentialPresence(vault)
    providers = ProviderRegistry.load(paths.config, log)
    attempts = AttemptRepo(sessions)
    attempts.expire_pending("daemon_restart")
    tokens = TokenManager(vault, providers, settings.connect, log)
    accounts = AccountRepo(sessions)
    policy_service = PolicyService(accounts, policy_repo, policy, bus, log)
    messages = MessageRepo(sessions)
    jobs = JobRepo(sessions)
    batches = BatchRepo(sessions)
    quota = QuotaRepo(sessions)
    send_attempts = SendAttemptRepo(sessions)
    for attempt in send_attempts.reserved_accepted():
        if attempt.account_id is None or attempt.quota_day is None:
            continue
        quota.commit(attempt.account_id, attempt.quota_day)
        send_attempts.set_quota(attempt.id, attempt.quota_day, "committed")
    reconcile_interrupted(send_attempts, log)
    stale = send_attempts.release_reserved()
    quota.reset_reservations()
    if stale:
        log.info("quota.reservations_reset", count=stale)
    runtime = RuntimeStateRepo(sessions)
    if runtime.clear_expired(utc_now()) is not None:
        log.info("service.resumed", reason="expired")
        bus.publish("service.resumed", {"reason": "expired"})
    transports = TransportRepo(sessions)
    oauth_clients = OAuthClientRepo(sessions)
    activity = ActivityRepo(sessions)
    counters = BatchCounterRepo(sessions)
    content = ContentStore(paths.data / "content")
    stats = StatsService(
        settings,
        activity,
        counters,
        batches,
        jobs,
        messages,
        accounts,
        quota,
        policy,
        log,
    )
    clients = OAuthClientService(
        oauth_clients,
        transports,
        accounts,
        vault,
        providers,
        bus,
        log,
    )
    return Foundation(
        settings=settings,
        paths=paths,
        log=log,
        engine=engine,
        sessions=sessions,
        events=events,
        bus=bus,
        connectivity_state=connectivity_state,
        policy=policy,
        policy_repo=policy_repo,
        policy_service=policy_service,
        vault=vault,
        presence=presence,
        providers=providers,
        attempts=attempts,
        tokens=tokens,
        accounts=accounts,
        messages=messages,
        jobs=jobs,
        batches=batches,
        quota=quota,
        send_attempts=send_attempts,
        runtime=runtime,
        transports=transports,
        oauth_clients=oauth_clients,
        activity=activity,
        counters=counters,
        content=content,
        stats=stats,
        clients=clients,
    )
