from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from downcroc.domain.events import Event
from downcroc.store.repositories.events import EventRepo


@dataclass(eq=False)
class Subscription:
    queue: asyncio.Queue[Event | None]
    closed: bool = False
    reason: str = "client"


class EventBus:
    def __init__(self, events: EventRepo, queue_size: int) -> None:
        self._events = events
        self._queue_size = queue_size
        self._subscribers: set[Subscription] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def publish(self, event_type: str, data: dict[str, Any]) -> Event:
        event = self._events.append(event_type, data)
        self.notify(event)
        return event

    def notify(self, event: Event) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        for subscription in list(self._subscribers):
            try:
                loop.call_soon_threadsafe(self._deliver, subscription, event)
            except RuntimeError:
                return

    @staticmethod
    def _deliver(subscription: Subscription, event: Event) -> None:
        if subscription.closed:
            return
        try:
            subscription.queue.put_nowait(event)
        except asyncio.QueueFull:
            subscription.closed = True
            subscription.reason = "slow"

    def subscribe(self) -> Subscription:
        subscription = Subscription(asyncio.Queue(self._queue_size))
        self._subscribers.add(subscription)
        return subscription

    def unsubscribe(self, subscription: Subscription) -> None:
        self._subscribers.discard(subscription)

    def close(self, subscription: Subscription, reason: str) -> None:
        if subscription.closed:
            return
        subscription.closed = True
        subscription.reason = reason
        try:
            subscription.queue.put_nowait(None)
        except asyncio.QueueFull:
            pass

    def close_all(self, reason: str) -> None:
        for subscription in list(self._subscribers):
            self.close(subscription, reason)
