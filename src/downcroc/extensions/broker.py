from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from downcroc.extensions.config import parse_grant
from downcroc.extensions.errors import CapabilityDenied
from downcroc.extensions.events import call_event
from downcroc.extensions.tiers import tier_for

if TYPE_CHECKING:
    from downcroc.core.bootstrap.services import Services
    from downcroc.extensions.config import ExtensionSettings
    from downcroc.extensions.store import ExtensionStore
    from downcroc.runtime.logging.setup import EventLogger

Handler = Callable[["Invocation", dict[str, Any]], Any]


@dataclass(frozen=True)
class Invocation:
    extension: str
    capability: str
    params: dict[str, Any]
    services: Services
    store: ExtensionStore
    log: EventLogger
    broker: Broker
    settings: ExtensionSettings
    grants: frozenset[str]
    settings_values: dict[str, Any]
    origin: str = "event"
    approved: bool = False

    def granted(self, capability: str) -> bool:
        if capability in self.grants:
            return True
        family = f"{capability.split('.', 1)[0]}.*"
        return family in self.grants

    def param(self, name: str, default: Any = None) -> Any:
        return self.params.get(name, default)


class Broker:
    def __init__(
        self,
        services: Services,
        store: ExtensionStore,
        log: EventLogger,
        settings: ExtensionSettings,
    ) -> None:
        self._services = services
        self._store = store
        self._log = log
        self._settings = settings
        self._handlers: dict[str, Handler] = {}
        self._calls: dict[str, deque[float]] = defaultdict(deque)
        self._sends: dict[str, deque[float]] = defaultdict(deque)
        self.loop: asyncio.AbstractEventLoop | None = None

    def register(self, names: tuple[str, ...], handler: Handler) -> None:
        for name in names:
            self._handlers[name] = handler

    @property
    def capabilities(self) -> tuple[str, ...]:
        return tuple(sorted(self._handlers))

    def call(
        self,
        extension: str,
        capability: str,
        params: dict[str, Any],
        grants: frozenset[str],
        settings: dict[str, Any],
        *,
        origin: str = "event",
        approved: bool = False,
    ) -> Any:
        started = time.monotonic()
        invocation = Invocation(
            extension,
            capability,
            params,
            self._services,
            self._store,
            self._log,
            self,
            self._settings,
            grants,
            settings,
            origin,
            approved,
        )
        try:
            self._authorize(invocation)
            handler = self._handlers.get(capability)
            if handler is None:
                raise CapabilityDenied(f"unknown capability {capability}")
            result = handler(invocation, params)
            self._log.info(
                "extension.call",
                **call_event(extension, capability, "ok", self._ms(started)),
            )
            return result
        except Exception as error:
            fields = {
                **call_event(extension, capability, "error", self._ms(started)),
                "error": type(error).__name__,
                "detail": str(error)[:200],
            }
            if isinstance(error, CapabilityDenied):
                self._log.info("extension.denied", **fields)
            else:
                self._log.info("extension.call_failed", **fields)
            raise

    def _authorize(self, invocation: Invocation) -> None:
        if tier_for(invocation.capability) == "elevated" and not invocation.approved:
            raise CapabilityDenied(
                f"capability {invocation.capability} needs an approved extension"
            )
        name, qualifier = parse_grant(invocation.capability)
        scoped = any(grant.partition(":")[0] == name for grant in invocation.grants)
        if (
            not invocation.granted(invocation.capability)
            and not invocation.granted(name)
            and not scoped
        ):
            raise CapabilityDenied(f"capability {invocation.capability} not granted")
        if (
            qualifier is not None
            and not invocation.granted(f"{name}:{qualifier}")
            and not invocation.granted(f"{name}:*")
        ):
            raise CapabilityDenied(f"target {qualifier} not granted")
        self._limit(
            self._calls[invocation.extension], self._settings.max_calls_per_min, 60
        )
        if name.startswith("mail.") or invocation.capability in {
            "job.create",
            "batch.submit",
        }:
            self._limit(
                self._sends[invocation.extension],
                self._settings.max_sends_per_hour,
                3600,
            )

    def _limit(self, stamps: deque[float], maximum: int, window: float) -> None:
        now = time.monotonic()
        while stamps and now - stamps[0] >= window:
            stamps.popleft()
        if len(stamps) >= maximum:
            raise CapabilityDenied("rate limit exceeded")
        stamps.append(now)

    def run(self, coro: Any) -> Any:
        if self.loop is None:
            raise RuntimeError("extension broker has no event loop")
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(
            self._settings.call_timeout_s
        )

    def _ms(self, started: float) -> int:
        return round((time.monotonic() - started) * 1000)
