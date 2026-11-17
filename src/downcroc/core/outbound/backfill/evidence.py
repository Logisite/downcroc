from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import timedelta

from downcroc.runtime.clock import parse_utc, utc_after, utc_now

BACKOFF_STEPS = (2.0, 5.0, 15.0, 60.0)
TIMEOUT_S = 30.0
MAX_BACKOFF_EXP = 20


@dataclass(frozen=True)
class Outcome:
    """What one stage-2 turn did to a hole."""

    state: str  # resolved | waiting | missing | unresolved | backoff | skipped
    reason: str | None = None
    scope: str | None = None
    next_check_at: str | None = None


@dataclass(frozen=True)
class Turn:
    """The search evidence for one hole, used by the log line."""

    sent_results: int = 0
    anywhere_results: int = 0
    provider_result: str = "not_attempted"


@dataclass(frozen=True)
class SearchFailure:
    """A lookup that did not complete after its backoff steps."""

    code: str
    detail: str
    auth: bool


@dataclass(frozen=True)
class ProviderLookup:
    """The exact messages.get fallback outcome for one hole."""

    state: str  # hit | missing | error | skipped | not_attempted
    thread_id: str | None = None
    error: str | None = None


def age_s(started_at: str) -> int:
    try:
        moment = parse_utc(started_at)
    except ValueError:
        return 0
    return max(0, int((parse_utc(utc_now()) - moment).total_seconds()))


def duration_ms(started: float) -> int:
    return round((time.monotonic() - started) * 1000)


def deadline(started_at: str, seconds: float) -> str:
    """The settle deadline measured from the send, not from this check."""

    try:
        moment = parse_utc(started_at) + timedelta(seconds=seconds)
    except ValueError:
        return utc_after(seconds)
    return moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def backoff_delay(check_count: int, base_s: float, max_s: float) -> float:
    exponent = min(max(check_count, 0), MAX_BACKOFF_EXP)
    return min(max_s, base_s * (2**exponent))
