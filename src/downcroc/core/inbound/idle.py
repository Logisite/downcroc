from __future__ import annotations

import imaplib
import queue
import time

from imap_tools.errors import ImapToolsError

from downcroc.core.inbound.signals import (
    WatcherEvent,
    WatcherHandle,
    WatchFailure,
)
from downcroc.domain.accounts import Account
from downcroc.runtime.config.schema import InboundSettings
from downcroc.runtime.logging.setup import EventLogger


class _IdleSession:
    """Idempotent IDLE wrapper so cleanup never sends DONE twice."""

    def __init__(self, box) -> None:
        self._box = box
        self.active = False

    def start(self) -> None:
        self._box.idle.start()
        self.active = True

    def stop(self) -> None:
        if not self.active:
            return
        self.active = False
        self._box.idle.stop()

    def noop(self) -> None:
        self._box.client.noop()

    def poll(self, timeout: float) -> list[bytes]:
        return self._box.idle.poll(timeout=timeout)


class IdleLoops:
    """IDLE liveness, heartbeat, and polling fallback for the IMAP watcher."""

    def __init__(
        self,
        queue_: queue.Queue[object],
        log: EventLogger,
        settings: InboundSettings,
    ) -> None:
        self._queue = queue_
        self._log = log
        self._settings = settings

    def idle(self, handle: WatcherHandle, box, account: Account) -> None:
        while not handle.stop.is_set():
            session = _IdleSession(box)
            try:
                session.start()
                started = time.monotonic()
                last_live = started
                reason: str | None = None
                try:
                    reason = self._poll_idle(handle, session, started, last_live)
                finally:
                    try:
                        session.stop()
                    except imaplib.IMAP4.error, OSError, ImapToolsError:
                        pass
            except (imaplib.IMAP4.error, OSError, ImapToolsError) as error:
                raise WatchFailure("imap_protocol_error") from error
            if reason is None:
                return
            self._wake_log(account.id, reason)
            return

    def _poll_idle(
        self,
        handle: WatcherHandle,
        session: _IdleSession,
        started: float,
        last_live: float,
    ) -> str | None:
        while not handle.stop.is_set():
            if handle.refresh.is_set():
                handle.refresh.clear()
                return "refresh"
            now = time.monotonic()
            remaining = self._settings.idle_timeout_s - (now - started)
            if remaining <= 0:
                return "timeout"
            heartbeat = self._settings.idle_heartbeat_s
            silent = now - last_live
            if silent >= heartbeat:
                try:
                    # NOOP is not allowed while IDLE is active: end IDLE,
                    # check liveness, then start IDLE again.
                    session.stop()
                    session.noop()
                    session.start()
                except (imaplib.IMAP4.error, OSError, ImapToolsError) as error:
                    handle.mode = "stale"
                    self._stale(handle, round(silent))
                    raise WatchFailure("imap_protocol_error") from error
                last_live = time.monotonic()
                started = last_live
                silent = 0.0
            responses = session.poll(
                timeout=min(1.0, remaining, max(0.1, heartbeat - silent))
            )
            if responses:
                joined = b" ".join(responses).upper()
                return "exists" if b"EXISTS" in joined else "change"
        return None

    def poll(self, handle: WatcherHandle, account: Account) -> None:
        deadline = time.monotonic() + self._settings.poll_interval_s
        while not handle.stop.is_set():
            if handle.refresh.is_set():
                handle.refresh.clear()
                self._wake_log(account.id, "refresh")
                return
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self._wake_log(account.id, "poll")
                return
            handle.stop.wait(timeout=min(1.0, remaining))

    def _stale(self, handle: WatcherHandle, silent_s: int) -> None:
        self._log.warning(
            "inbound.idle_stale",
            account=handle.account.id,
            silent_s=silent_s,
        )
        self._queue.put(
            WatcherEvent(
                "inbound.idle_stale",
                {"account": handle.account.id, "silent_s": silent_s},
            )
        )

    def _wake_log(self, account_id: str, reason: str) -> None:
        self._log.info("watcher.idle_wake", account=account_id, reason=reason)
        self._queue.put(
            WatcherEvent(
                "watcher.idle_wake",
                {"account": account_id, "reason": reason},
            )
        )
