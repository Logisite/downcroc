from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI

from downcroc.api.routes import health
from downcroc.runtime.config.schema import Settings
from downcroc.runtime.logging.setup import EventLogger
from downcroc.runtime.paths import Paths
from downcroc.version import API_VERSION, __version__


def create_app(settings: Settings, paths: Paths, log: EventLogger) -> FastAPI:
    boot = time.monotonic()
    started_at = time.time()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        log.info(
            "daemon.ready",
            port=settings.daemon.port,
            boot_ms=round((time.monotonic() - boot) * 1000),
        )
        yield

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
    app.include_router(health.router)
    return app
