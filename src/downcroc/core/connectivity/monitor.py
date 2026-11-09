from __future__ import annotations

import threading
import time

from downcroc.core.connectivity.probe import probe_once
from downcroc.core.connectivity.settings import ConnectivitySettings
from downcroc.core.connectivity.state import ConnectivityState
from downcroc.core.events import EventBus
from downcroc.runtime.clock import utc_now
from downcroc.runtime.logging.setup import EventLogger


class ConnectivityMonitor:
    """Probe loop that flips ConnectivityState after confirmed outages.

    A single failed probe never flips the state. The state only changes
    after several consecutive probes in the same direction, spaced by the
    configured interval plus jitter, so a brief blip never pauses or
    resumes anything. The monitor starts optimistic (online).
    """

    def __init__(
        self,
        settings: ConnectivitySettings,
        state: ConnectivityState,
        bus: EventBus,
        log: EventLogger,
    ) -> None:
        self._settings = settings
        self._state = state
        self._bus = bus
        self._log = log
        self._failures = 0
        self._successes = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def pending_failures(self) -> int:
        return self._failures

    def start(self) -> None:
        if not self._settings.enabled or self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run, name="downcroc-connectivity", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread, self._thread = self._thread, None
        if thread is not None:
            thread.join(timeout=max(1.0, self._settings.timeout_s * 2))

    def _run(self) -> None:
        settings = self._settings
        while not self._stop.is_set():
            ok = probe_once(
                settings.probe_host, settings.probe_port, settings.timeout_s
            )
            self._observe(ok)
            jitter = 0.0
            if settings.jitter_s:
                jitter = time.monotonic() % settings.jitter_s
            self._stop.wait(timeout=settings.interval_s + jitter)

    def _observe(self, ok: bool) -> None:
        settings = self._settings
        if ok:
            self._failures = 0
            self._successes += 1
        else:
            self._successes = 0
            self._failures += 1
        online = self._state.online
        flip = ok and not online and self._successes >= settings.confirm_successes
        flip = flip or (
            not ok and online and self._failures >= settings.confirm_failures
        )
        if not ok and self._failures < settings.confirm_failures and online:
            self._log.debug(
                "connectivity.probe_failed",
                host=settings.probe_host,
                failures=self._failures,
                needed=settings.confirm_failures,
            )
        if not flip:
            return
        self._state.set(ok, utc_now())
        event = "connectivity.up" if ok else "connectivity.down"
        self._log.info(
            event,
            host=settings.probe_host,
            port=settings.probe_port,
            probes=self._successes if ok else self._failures,
        )
        self._bus.publish(event, {"host": settings.probe_host})
