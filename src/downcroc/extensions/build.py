from __future__ import annotations

from typing import TYPE_CHECKING

from downcroc.extensions.broker import Broker
from downcroc.extensions.host import ExtensionHost
from downcroc.extensions.manifest import load_manifests
from downcroc.extensions.store import ExtensionStore
from downcroc.runtime.logging.setup import EventLogger

if TYPE_CHECKING:
    from downcroc.core.bootstrap.services import Services
    from downcroc.extensions.config import ExtensionSettings
    from downcroc.runtime.paths import Paths


def build_host(
    services: Services,
    paths: Paths,
    settings: ExtensionSettings,
    log: EventLogger,
) -> ExtensionHost:
    directory = paths.config / settings.dir
    store = ExtensionStore(services.sessions)
    broker = Broker(services, store, log, settings)
    from downcroc.extensions.capabilities import register_capabilities

    register_capabilities(broker)
    host = ExtensionHost(
        paths,
        settings,
        load_manifests(directory),
        broker,
        store,
        log,
        services.bus,
    )
    services.extensions = host
    return host
