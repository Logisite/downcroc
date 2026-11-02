from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from downcroc.domain.accounts import Account
from downcroc.store.repositories.messages import IngestResult

FOLDER = "INBOX"
STOP = object()


@dataclass
class IngestJob:
    account_id: str
    incoming: Any
    done: threading.Event = field(default_factory=threading.Event)
    result: IngestResult | None = None
    error: BaseException | None = None


@dataclass
class CursorJob:
    account_id: str
    uidvalidity: int
    last_uid: int
    reset: bool
    done: threading.Event = field(default_factory=threading.Event)
    error: BaseException | None = None


@dataclass
class HistoryJob:
    account_id: str
    history_id: str
    synced_at: str
    done: threading.Event = field(default_factory=threading.Event)
    error: BaseException | None = None


@dataclass(frozen=True)
class WatcherState:
    account_id: str
    ok: bool
    host: str = ""
    uidvalidity: int = 0
    reason: str = ""
    retry_in_s: int = 0
    needs_reauth: bool = False
    source: str = "imap"
    mode: str = ""
    project_id: str | None = None
    silent_s: int = 0


@dataclass(frozen=True)
class WatcherEvent:
    event: str
    data: dict[str, Any]


@dataclass
class SyncWaiter:
    done: threading.Event = field(default_factory=threading.Event)
    ok: bool = False
    reason: str = ""


@dataclass
class WatcherHandle:
    account: Account
    stop: threading.Event = field(default_factory=threading.Event)
    refresh: threading.Event = field(default_factory=threading.Event)
    sync_waiters: list[SyncWaiter] = field(default_factory=list)
    failures: int = 0
    next_start: float = 0.0
    blocked: str | None = None
    stop_reason: str | None = None
    source: str = "imap"
    mode: str = "starting"
    allow_idle: bool = True
    last_event_at: str | None = None
    thread: threading.Thread | None = None


class Stopped(Exception):
    pass


class WatchFailure(Exception):
    def __init__(
        self,
        reason: str,
        *,
        needs_reauth: bool = False,
        fatal: bool = False,
        project_id: str | None = None,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.needs_reauth = needs_reauth
        self.fatal = fatal
        self.project_id = project_id
