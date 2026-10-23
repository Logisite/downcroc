from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from downcroc.core.accounts_service import AccountsService
from downcroc.core.events import EventBus
from downcroc.core.inbound_service import InboundService
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
from downcroc.store.repositories.attempts import AttemptRepo
from downcroc.store.repositories.events import EventRepo
from downcroc.store.repositories.messages import MessageRepo


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
    content = ContentStore(paths.data / "content")
    inbound = InboundService(
        account_repo,
        message_repo,
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
    inbound.open()
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
    )
