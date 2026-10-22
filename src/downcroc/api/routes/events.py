from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Query, Request
from starlette.responses import StreamingResponse

from downcroc.domain.events import Event

router = APIRouter(tags=["events"])

REPLAY_BATCH = 500


def _client(request: Request) -> str:
    if request.client is None:
        return "unknown"
    return f"{request.client.host}:{request.client.port}"


def _frame(event: Event) -> str:
    data = {"ts": event.ts, **event.data}
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"id: {event.seq}\nevent: {event.type}\ndata: {payload}\n\n"


def _gap(requested: int, oldest: int | None) -> str:
    data = json.dumps(
        {"requested_id": requested, "oldest_id": oldest},
        separators=(",", ":"),
    )
    return f"event: gap\ndata: {data}\n\n"


@router.get("/api/events")
async def stream_events(
    request: Request,
    last_event_id: str | None = Query(default=None),
) -> StreamingResponse:
    services = request.app.state.services
    settings = request.app.state.settings
    log = request.app.state.log
    bus = services.bus
    events = services.events
    keepalive = settings.events.keepalive_s
    raw_id = request.headers.get("last-event-id") or last_event_id

    requested: int | None = None
    if raw_id is not None:
        try:
            requested = int(raw_id)
        except ValueError:
            requested = None

    async def stream() -> AsyncIterator[str]:
        subscription = bus.subscribe()
        log.info("sse.connected", client=_client(request), last_event_id=raw_id)
        sent: int | None = None
        try:
            if requested is not None:
                oldest, newest = events.bounds()
                if newest is None:
                    log.warning("event.gap", requested_id=requested, oldest_id=None)
                    yield _gap(requested, None)
                elif requested > newest or requested < oldest - 1:
                    log.warning("event.gap", requested_id=requested, oldest_id=oldest)
                    yield _gap(requested, oldest)
                    sent = requested
                else:
                    cursor = requested
                    while True:
                        batch = events.after(cursor, REPLAY_BATCH)
                        if not batch:
                            break
                        for event in batch:
                            cursor = event.seq
                            sent = event.seq
                            yield _frame(event)

            while True:
                if subscription.closed:
                    break
                try:
                    event = await asyncio.wait_for(
                        subscription.queue.get(), timeout=keepalive
                    )
                except TimeoutError:
                    if subscription.closed:
                        break
                    yield ": keepalive\n\n"
                    continue
                if event is None:
                    break
                if sent is not None and event.seq <= sent:
                    continue
                sent = event.seq
                yield _frame(event)
        finally:
            bus.unsubscribe(subscription)
            log.info("sse.disconnected", reason=subscription.reason)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
