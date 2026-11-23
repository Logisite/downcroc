from __future__ import annotations

import asyncio
import os
import time
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI

from downcroc.api import errors
from downcroc.api.auth import ApiAuthMiddleware
from downcroc.api.middleware import RequestLogMiddleware
from downcroc.api.routes import (
    accounts,
    attempts,
    backfill,
    backups,
    batches,
    config,
    doctor,
    events,
    failed,
    followups,
    health,
    jobs,
    messages,
    oauth_clients,
    policy,
    providers,
    service,
    stats,
    transports,
    vault,
)
from downcroc.core.bootstrap import build
from downcroc.extensions.api import router as extension_router
from downcroc.runtime.config.schema import Settings
from downcroc.runtime.logging.setup import EventLogger
from downcroc.runtime.paths import Paths
from downcroc.store.db.migrate import MigrationFailed
from downcroc.version import API_VERSION, __version__


def create_app(
    settings: Settings,
    paths: Paths,
    log: EventLogger,
    token: str = "",
) -> FastAPI:
    boot = time.monotonic()
    started_at = time.time()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            services = build(settings, paths, log)
        except MigrationFailed as error:
            # Keep startup failures short and structured. A raw alembic
            # traceback here made the real cause invisible in the JSONL log.
            log.error(
                "daemon.start_failed",
                reason="db_migration_failed",
                detail=error.message,
                hint=error.hint or "",
            )
            raise SystemExit(error.message) from None
        except Exception as error:
            log.error(
                "daemon.start_failed",
                reason="bootstrap_failed",
                error=type(error).__name__,
                detail=str(error)[:300],
                traceback=traceback.format_exc()[-4000:],
            )
            raise
        app.state.services = services
        app.state.config = services.config
        loop = asyncio.get_running_loop()
        services.bus.start(loop)
        host = services.extensions
        pump: asyncio.Task[None] | None = None
        if host is not None:
            host.broker.loop = loop
            host.start()
            pump = asyncio.create_task(host.pump())
        services.dispatcher.start()
        services.retention.start()
        services.config.start()
        services.backfill.start()
        log.info(
            "daemon.ready",
            port=settings.daemon.port,
            boot_ms=round((time.monotonic() - boot) * 1000),
        )
        try:
            yield
        finally:
            if pump is not None:
                pump.cancel()
            if host is not None:
                host.stop()
            await services.config.stop()
            await services.retention.stop()
            await services.dispatcher.stop()
            await services.backfill.stop()
            await services.auth_preflight.stop()
            await services.outbound.close_sessions("shutdown")
            services.inbound.stop_all("shutdown")
            services.accounts.close_flows("daemon_stopped")
            services.vault.lock("shutdown")
            services.bus.close_all("shutdown")
            services.close()

    app = FastAPI(
        title="downcroc",
        version=__version__,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.add_middleware(
        ApiAuthMiddleware,
        token=token,
        settings=settings,
        log=log,
    )
    app.add_middleware(RequestLogMiddleware, log=log)
    app.state.settings = settings
    app.state.paths = paths
    app.state.log = log
    app.state.request_shutdown = lambda: None
    app.state.pid = os.getpid()
    app.state.started = boot
    app.state.started_at = started_at
    app.state.api_version = API_VERSION
    errors.install(app)
    app.include_router(service.router)
    app.include_router(health.router)
    app.include_router(vault.router)
    app.include_router(config.router)
    app.include_router(accounts.router)
    app.include_router(policy.router)
    app.include_router(transports.router)
    app.include_router(oauth_clients.router)
    app.include_router(attempts.router)
    app.include_router(backfill.router)
    app.include_router(doctor.router)
    app.include_router(providers.router)
    app.include_router(messages.router)
    app.include_router(jobs.router)
    app.include_router(batches.router)
    app.include_router(followups.router)
    app.include_router(followups.outlook_router)
    app.include_router(failed.router)
    app.include_router(failed.aliases)
    app.include_router(stats.router)
    app.include_router(backups.router)
    app.include_router(events.router)
    app.include_router(extension_router)
    return app
