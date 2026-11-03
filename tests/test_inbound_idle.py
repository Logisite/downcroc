from __future__ import annotations

import imaplib
import queue
import threading
from types import SimpleNamespace

import pytest

from downcroc.core.inbound import idle
from downcroc.core.inbound.idle import IdleLoops
from downcroc.core.inbound.signals import WatchFailure
from downcroc.runtime.config.sections_mail import InboundSettings


class _FakeClient:
    def __init__(self, *, noop_error: Exception | None = None) -> None:
        self.noops = 0
        self._noop_error = noop_error

    def noop(self) -> None:
        self.noops += 1
        if self._noop_error is not None:
            raise self._noop_error


class _FakeIdle:
    def __init__(self, responses: list[bytes]) -> None:
        self.starts = 0
        self.stops = 0
        self._responses = responses

    def start(self) -> None:
        self.starts += 1

    def stop(self) -> None:
        self.stops += 1

    def poll(self, timeout: float) -> list[bytes]:
        return self._responses


class _FakeBox:
    def __init__(
        self,
        *,
        responses: list[bytes],
        noop_error: Exception | None = None,
    ) -> None:
        self.client = _FakeClient(noop_error=noop_error)
        self.idle = _FakeIdle(responses)


class _FakeLog:
    def info(self, *args: object, **kwargs: object) -> None:
        pass

    def warning(self, *args: object, **kwargs: object) -> None:
        pass


def _loops() -> IdleLoops:
    return IdleLoops(
        queue.Queue(),
        _FakeLog(),  # type: ignore[arg-type]
        InboundSettings(idle_heartbeat_s=30, idle_timeout_s=60),
    )


def _handle() -> SimpleNamespace:
    return SimpleNamespace(
        stop=threading.Event(),
        refresh=threading.Event(),
        mode="idle",
        account=SimpleNamespace(id="acct_test"),
    )


def _clock(monkeypatch: pytest.MonkeyPatch) -> None:
    values = iter([0.0, 31.0, 31.0, 31.0, 31.0])
    monkeypatch.setattr(idle.time, "monotonic", lambda: next(values))


def test_idle_heartbeat_sends_noop_and_restarts_idle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    box = _FakeBox(responses=[b"* 1 EXISTS"])
    _clock(monkeypatch)

    _loops().idle(_handle(), box, SimpleNamespace(id="acct_test"))

    assert box.client.noops == 1
    assert box.idle.starts == 2
    assert box.idle.stops == 2


def test_idle_heartbeat_failure_does_not_send_done_twice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    box = _FakeBox(
        responses=[b"* 1 EXISTS"],
        noop_error=imaplib.IMAP4.error("NOOP failed"),
    )
    _clock(monkeypatch)

    with pytest.raises(WatchFailure) as failure:
        _loops().idle(_handle(), box, SimpleNamespace(id="acct_test"))

    assert failure.value.reason == "imap_protocol_error"
    assert box.idle.stops == 1
