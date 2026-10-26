from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from downcroc.core.accounts_service import AccountsService
from downcroc.core.batches import BatchesService
from downcroc.core.dispatch import Dispatcher, FailureLog, FailureService
from downcroc.core.events import EventBus
from downcroc.core.followups import FollowUpService
from downcroc.core.inbound import InboundService
from downcroc.core.outbound import OutboundService
from downcroc.core.retention import RetentionService
from downcroc.core.stats import StatsService
from downcroc.core.vault_service import VaultService
from downcroc.domain.accounts import SendPolicy
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
from downcroc.store.repositories.quota import QuotaRepo


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
    inbound: InboundService
    outbound: OutboundService
    batches: BatchesService
    followups: FollowUpService
    stats: StatsService
    retention: RetentionService
    failures: FailureService
    dispatcher: Dispatcher

    def close(self) -> None:
        self.inbound.close()
        self.engine.dispose()


def build(settings: Settings, paths: Paths, log: EventLogger) -> Services:
    engine = open_database(paths.data / "downcroc.db")
    run_migrations(engine, log)
    sessions = sessions_for(engine)
    events = EventRepo(sessions, settings.events.ring_size)
    bus = EventBus(events, settings.events.queue_size)
    policy = SendPolicy(
        daily_allowance=settings.sending.daily_allowance,
        window_start=settings.sending.window_start,
        window_end=settings.sending.window_end,
        jitter_min=settings.sending.jitter_min,
        jitter_max=settings.sending.jitter_max,
        max_in_flight=settings.sending.max_in_flight,
        enabled=settings.sending.enabled,
    )
    vault = VaultService(paths.data / "vault.enc", settings.vault, bus, log)
    providers = ProviderRegistry.load(paths.config, log)
    attempts = AttemptRepo(sessions)
    attempts.expire_pending("daemon_restart")
    tokens = TokenManager(vault, providers, settings.connect, log)
    account_repo = AccountRepo(sessions)
    message_repo = MessageRepo(sessions)
    job_repo = JobRepo(sessions)
    batch_repo = BatchRepo(sessions)
    quota_repo = QuotaRepo(sessions)
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
        log,
    )
    inbound = InboundService(
        account_repo,
        message_repo,
        stats,
        providers,
        vault,
        tokens,
        content,
        bus,
        log,
        settings.inbound,
        settings.connect,
    )
    accounts = AccountsService(
        account_repo,
        bus,
        log,
        policy,
        providers,
        vault,
        tokens,
        attempts,
        settings.connect,
        inbound,
    )
    outbound = OutboundService(
        job_repo,
        account_repo,
        providers,
        vault,
        tokens,
        content,
        stats,
        bus,
        log,
        settings.outbound,
        settings.connect,
    )
    inbound.open()
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
        settings.dispatch,
        settings.outbound.lease_seconds,
        job_repo,
        account_repo,
        batch_repo,
        quota_repo,
        failures,
        followups,
        outbound,
        vault,
        bus,
        log,
        settings.followups.check_s,
    )
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
        inbound=inbound,
        outbound=outbound,
        batches=batches,
        followups=followups,
        stats=stats,
        retention=retention,
        failures=failures,
        dispatcher=dispatcher,
    )
