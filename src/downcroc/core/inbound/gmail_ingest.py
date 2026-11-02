from __future__ import annotations

import queue
import threading
import time

from downcroc.core.inbound.signals import IngestJob, Stopped, WatchFailure
from downcroc.domain.messages import IncomingMessage
from downcroc.domain.providers import ProviderSpec
from downcroc.mail.gmail.parse import parse_raw
from downcroc.mail.gmail.read import get_message


def fetch_incoming(
    spec: ProviderSpec,
    token: str,
    provider_id: str,
    *,
    api_timeout_s: float,
    project_id: str | None,
    body_max_bytes: int,
) -> IncomingMessage | None:
    message = get_message(
        spec,
        token,
        provider_id,
        timeout_s=api_timeout_s,
        fmt="raw",
        project_id=project_id,
    )
    if message.raw is None:
        return None
    return parse_raw(message.raw, provider_id, body_max_bytes)


def enqueue_ingest(
    queue_: queue.Queue[object],
    account_id: str,
    incoming: IncomingMessage,
    stop: threading.Event,
    timeout_s: float,
) -> bool:
    job = IngestJob(account_id=account_id, incoming=incoming)
    queue_.put(job)
    if not wait_done(job.done, stop, timeout_s):
        raise Stopped
    if job.error is not None:
        raise WatchFailure("ingest_failed")
    return True


def wait_done(
    done: threading.Event,
    stop: threading.Event,
    timeout_s: float,
) -> bool:
    deadline = time.monotonic() + timeout_s
    while not done.wait(0.2):
        if stop.is_set():
            return False
        if time.monotonic() >= deadline:
            raise WatchFailure("ingest_timeout")
    return True
