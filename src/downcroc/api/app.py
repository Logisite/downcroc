from __future__ import annotations

import asyncio
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI

from downcroc.api import errors
from downcroc.api.routes import (
    accounts,
    attempts,
    events,
    health,
    messages,
    providers,
    vault,
)
from downcroc.core.bootstrap import build
from downcroc.runtime.config.schema import Settings
from downcroc.runtime.logging.setup import EventLogger
from downcroc.runtime.paths import Paths
from downcroc.version import API_VERSION, __version__


def create_app(settings: Settings, paths: Paths, log: EventLogger) -> FastAPI:
    boot = time.monotonic()
    started_at = time.time()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        services = build(settings, paths, log)
        app.state.services = services
        services.bus.start(asyncio.get_running_loop())
        log.info(
            "daemon.ready",
            port=settings.daemon.port,
            boot_ms=round((time.monotonic() - boot) * 1000),
        )
        try:
            yield
        finally:
            services.inbound.stop_all("shutdown")
            services.accounts.close_flows("daemon_stopped")
            services.vault.lock("shutdown")
            services.bus.close_all("shutdown")
            services.close()

    app = FastAPI(
        title="downcroc",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.paths = paths
    app.state.log = log
    app.state.pid = os.getpid()
    app.state.started = boot
    app.state.started_at = started_at
    app.state.api_version = API_VERSION
    errors.install(app)
    app.include_router(health.router)
    app.include_router(vault.router)
    app.include_router(accounts.router)
    app.include_router(attempts.router)
    app.include_router(providers.router)
    app.include_router(messages.router)
    app.include_router(events.router)
    return app
