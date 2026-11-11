from __future__ import annotations

import time
import traceback
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from downcroc.runtime.logging import correlation
from downcroc.runtime.logging.setup import EventLogger


class RequestLogMiddleware:
    """One structured request event, without bodies, headers, or tokens."""

    def __init__(self, app: ASGIApp, log: EventLogger) -> None:
        self.app = app
        self.log = log

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = uuid.uuid4().hex[:16]
        token = correlation.set_current(request_id)
        started = time.monotonic()
        status = 500
        code: str | None = None

        async def capture(message: Message) -> None:
            nonlocal status, code
            if message["type"] == "http.response.start":
                status = int(message["status"])
                headers = {
                    key.decode("latin-1").lower(): value.decode("latin-1")
                    for key, value in message.get("headers", [])
                }
                code = headers.get("x-downcroc-error")
                message.setdefault("headers", []).append(
                    (b"x-request-id", request_id.encode("ascii"))
                )
            await send(message)

        try:
            await self.app(scope, receive, capture)
        except Exception as error:
            self.log.error(
                "api.request_failed",
                method=scope.get("method", ""),
                path=scope.get("path", ""),
                status=500,
                error=error.__class__.__name__,
                detail=str(error)[:300],
                duration_ms=round((time.monotonic() - started) * 1000),
                request_id=request_id,
                traceback=traceback.format_exc()[-4000:],
            )
            raise
        else:
            if status >= 400:
                self.log.warning(
                    "api.request_failed",
                    method=scope.get("method", ""),
                    path=scope.get("path", ""),
                    status=status,
                    code=code,
                    duration_ms=round((time.monotonic() - started) * 1000),
                    request_id=request_id,
                )
        finally:
            correlation.reset(token)
