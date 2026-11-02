from __future__ import annotations

import time
from dataclasses import dataclass, field

from downcroc.domain.transports import AccountTransport
from downcroc.runtime.config.schema import DispatchSettings


@dataclass
class _Bucket:
    capacity: float
    rate_per_s: float
    tokens: float
    updated: float

    @classmethod
    def of(cls, rate_per_min: int, now: float) -> _Bucket:
        capacity = float(max(1, rate_per_min))
        return cls(capacity, capacity / 60.0, capacity, now)

    def take(self, now: float) -> bool:
        self.tokens = min(
            self.capacity,
            self.tokens + max(0.0, now - self.updated) * self.rate_per_s,
        )
        self.updated = now
        if self.tokens < 1.0:
            return False
        self.tokens -= 1.0
        return True


@dataclass
class _Binding:
    limit: int
    in_flight: int = 0
    bucket: _Bucket | None = None
    last_grant: int = 0


@dataclass
class _State:
    in_flight: int = 0
    smtp_in_flight: int = 0
    bindings: dict[str, _Binding] = field(default_factory=dict)
    granted: int = 0
    account_turn: dict[str, int] = field(default_factory=dict)


class TransportLimiter:
    """Non-blocking per-binding and global capacity for send attempts.

    Two independent rules apply:

    - ``dispatch.parallel_sends`` is off by default, so only one send is in
      flight at a time across the whole fleet.
    - SMTP is always serial: a seat is one authenticated connection, and a
      second SMTP send waits even when the fleet has several seats. Seats
      rotate; they never overlap.
    """

    def __init__(
        self,
        dispatch: DispatchSettings,
        clock=time.monotonic,
    ) -> None:
        self._dispatch = dispatch
        self._state = _State()
        self._clock = clock

    @property
    def parallel(self) -> bool:
        return bool(self._dispatch.parallel_sends)

    def effective_global(self) -> int:
        if not self.parallel:
            return 1
        return max(1, self._dispatch.global_in_flight)

    def effective_limit(self, binding: AccountTransport) -> int:
        if binding.seat:
            return 1
        if not self.parallel:
            return 1
        return max(
            1,
            min(binding.max_concurrency, self._dispatch.api_max_concurrency),
        )

    def _lane(self, binding: AccountTransport, now: float) -> _Binding:
        state = self._state.bindings.get(binding.id)
        if state is None:
            limit = self.effective_limit(binding)
            bucket = (
                _Bucket.of(binding.rate_per_min, now)
                if binding.rate_per_min and not binding.seat
                else None
            )
            state = _Binding(limit=limit, bucket=bucket)
            self._state.bindings[binding.id] = state
        else:
            state.limit = self.effective_limit(binding)
        return state

    def acquire(self, binding: AccountTransport) -> bool:
        now = self._clock()
        state = self._state
        lane = self._lane(binding, now)
        if lane.in_flight >= lane.limit:
            return False
        if state.in_flight >= self.effective_global():
            return False
        if binding.seat and state.smtp_in_flight >= 1:
            return False
        if lane.bucket is not None and not lane.bucket.take(now):
            return False
        lane.in_flight += 1
        state.in_flight += 1
        if binding.seat:
            state.smtp_in_flight += 1
        state.granted += 1
        lane.last_grant = state.granted
        state.account_turn[binding.account_id] = state.granted
        return True

    def release(self, binding: AccountTransport) -> None:
        state = self._state
        lane = state.bindings.get(binding.id)
        if lane is not None and lane.in_flight > 0:
            lane.in_flight -= 1
        if state.in_flight > 0:
            state.in_flight -= 1
        if binding.seat and state.smtp_in_flight > 0:
            state.smtp_in_flight -= 1

    def forget(self, binding_id: str) -> None:
        lane = self._state.bindings.pop(binding_id, None)
        if lane is not None:
            self._state.in_flight = max(0, self._state.in_flight - lane.in_flight)

    def lanes(self, binding: AccountTransport) -> int:
        return self.effective_limit(binding)

    def smtp_busy(self) -> bool:
        return self._state.smtp_in_flight > 0

    def last_grant(self, binding_id: str) -> int:
        lane = self._state.bindings.get(binding_id)
        return lane.last_grant if lane is not None else 0

    def account_turn(self, account_id: str) -> int:
        return self._state.account_turn.get(account_id, 0)

    def snapshot(self) -> dict[str, int]:
        return {
            "global_limit": self.effective_global(),
            "in_flight": self._state.in_flight,
            "smtp_in_flight": self._state.smtp_in_flight,
            "parallel": int(self.parallel),
        }

    def in_flight(self, binding_id: str) -> int:
        lane = self._state.bindings.get(binding_id)
        return lane.in_flight if lane is not None else 0
