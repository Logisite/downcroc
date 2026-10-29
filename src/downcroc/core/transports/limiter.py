from __future__ import annotations

import time
from dataclasses import dataclass, field

from downcroc.domain.transports import AccountTransport


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
    global_limit: int
    in_flight: int = 0
    bindings: dict[str, _Binding] = field(default_factory=dict)
    granted: int = 0
    account_turn: dict[str, int] = field(default_factory=dict)

    def binding(self, binding: AccountTransport, now: float) -> _Binding:
        state = self.bindings.get(binding.id)
        if state is None:
            limit = 1 if binding.seat else max(1, binding.max_concurrency)
            bucket = (
                _Bucket.of(binding.rate_per_min, now)
                if binding.rate_per_min and not binding.seat
                else None
            )
            state = _Binding(limit=limit, bucket=bucket)
            self.bindings[binding.id] = state
        return state


class TransportLimiter:
    """Non-blocking per-binding and global capacity for send attempts."""

    def __init__(self, global_in_flight: int, clock=time.monotonic) -> None:
        self._state = _State(global_limit=max(1, global_in_flight))
        self._clock = clock

    def acquire(self, binding: AccountTransport) -> bool:
        now = self._clock()
        state = self._state
        lane = state.binding(binding, now)
        if lane.in_flight >= lane.limit:
            return False
        if state.in_flight >= state.global_limit:
            return False
        if lane.bucket is not None and not lane.bucket.take(now):
            return False
        lane.in_flight += 1
        state.in_flight += 1
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

    def forget(self, binding_id: str) -> None:
        lane = self._state.bindings.pop(binding_id, None)
        if lane is not None:
            self._state.in_flight = max(0, self._state.in_flight - lane.in_flight)

    def lanes(self, binding: AccountTransport) -> int:
        return 1 if binding.seat else max(1, binding.max_concurrency)

    def snapshot(self) -> dict[str, int]:
        return {
            "global_limit": self._state.global_limit,
            "in_flight": self._state.in_flight,
        }

    def in_flight(self, binding_id: str) -> int:
        lane = self._state.bindings.get(binding_id)
        return lane.in_flight if lane is not None else 0
