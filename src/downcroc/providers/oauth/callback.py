from __future__ import annotations

import hmac
import html
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Protocol
from urllib.parse import parse_qs, urlparse

from sqlalchemy.exc import SQLAlchemyError

from downcroc.domain.attempts import AttemptState, ConnectAttempt
from downcroc.domain.errors import DomainError
from downcroc.domain.providers import ProviderSpec
from downcroc.providers.oauth import client as oauth_client
from downcroc.runtime.clock import parse_utc, utc_now
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.repositories.attempts import AttemptRepo

CALLBACK_PATH = "/callback"
ERROR_CODE = re.compile(r"^[a-z0-9_]{1,64}$")
POLL_SECONDS = 0.5
PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root {{ color-scheme: dark; }}
body {{ margin: 0; min-height: 100vh; display: grid; place-items: center;
background: #14110f; color: #f2ece5;
font: 16px/1.55 ui-sans-serif, system-ui, sans-serif; }}
main {{ max-width: 30rem; padding: 2rem; }}
h1 {{ margin: 0 0 0.5rem; font-size: 1.3rem; }}
p {{ margin: 0.4rem 0 0; color: #b9afa4; }}
code {{ color: #e8d9c8; }}
</style>
</head>
<body><main><h1>{title}</h1><p>{message}</p>{detail}</main></body>
</html>
"""
OnCode = Callable[[ConnectAttempt, ProviderSpec, str, str, str], None]


class CallbackFlow(Protocol):
    attempts: AttemptRepo
    log: EventLogger
    on_code: OnCode


@dataclass
class Listener:
    attempt: ConnectAttempt
    spec: ProviderSpec
    redirect_uri: str
    verifier: str
    server: HTTPServer
    stop: threading.Event
    flow: CallbackFlow
    thread: threading.Thread | None = None


class CallbackServer(HTTPServer):
    owner: Listener
    allow_reuse_address = False

    def __init__(self, server_address: tuple[str, int]) -> None:
        super().__init__(server_address, CallbackHandler)
        self.timeout = POLL_SECONDS


class CallbackHandler(BaseHTTPRequestHandler):
    server: CallbackServer

    def do_GET(self) -> None:
        handle_callback(self.server.owner, self)

    def log_message(self, format: str, *args: Any) -> None:
        return


def handle_callback(listener: Listener, handler: BaseHTTPRequestHandler) -> None:
    flow = listener.flow
    parsed = urlparse(handler.path)
    if parsed.path != CALLBACK_PATH:
        respond(handler, 404, "Not found", "This is not a callback path.")
        return
    query = parse_qs(parsed.query, keep_blank_values=True)
    state = first(query, "state")
    state_ok = hmac.compare_digest(state, listener.attempt.state_token)
    flow.log.info(
        "oauth.callback",
        state_ok=state_ok,
        elapsed_ms=elapsed_ms(listener.attempt.created_at),
        attempt=listener.attempt.id,
        account=listener.attempt.account_id,
    )
    if not state_ok:
        respond(
            handler,
            400,
            "Callback rejected",
            "This callback does not match a pending connect attempt.",
        )
        return
    current = flow.attempts.get(listener.attempt.id)
    if current.state is not AttemptState.PENDING:
        respond(
            handler,
            409,
            "Attempt finished",
            "This connect attempt has already finished.",
        )
        return
    if parse_utc(utc_now()) >= parse_utc(listener.attempt.expires_at):
        flow.attempts.set_state(listener.attempt.id, AttemptState.EXPIRED, "expired")
        flow.log.warning(
            "oauth.failed",
            code="expired",
            attempt=listener.attempt.id,
            account=listener.attempt.account_id,
        )
        listener.stop.set()
        respond(
            handler,
            410,
            "Attempt expired",
            "This connect attempt expired. Start a new one.",
            "expired",
        )
        return
    error = first(query, "error")
    if error:
        fail(flow, listener, error_code(error))
        respond(
            handler,
            200,
            "Authorization not granted",
            "downcroc did not receive permission to connect the mailbox.",
            error_code(error),
        )
        return
    code = first(query, "code")
    if not code:
        fail(flow, listener, "oauth_no_code")
        respond(
            handler,
            400,
            "Callback incomplete",
            "The provider did not return an authorization code.",
            "oauth_no_code",
        )
        return
    try:
        flow.on_code(
            listener.attempt,
            listener.spec,
            code,
            listener.redirect_uri,
            listener.verifier,
        )
    except DomainError as failure:
        fail(flow, listener, failure.code)
        respond(
            handler,
            502,
            "Connection failed",
            "downcroc could not verify the mailbox. Return and try again.",
            failure.code,
        )
        return
    except oauth_client.OAuthError as failure:
        fail(flow, listener, failure.code)
        respond(
            handler,
            502,
            "Connection failed",
            "The provider rejected the authorization. Return and try again.",
            failure.code,
        )
        return
    except oauth_client.OAuthUnavailableError:
        fail(flow, listener, "oauth_unavailable")
        respond(
            handler,
            502,
            "Provider unreachable",
            "The provider could not be reached. Return and try again.",
            "oauth_unavailable",
        )
        return
    except (
        SQLAlchemyError,
        OSError,
        RuntimeError,
        ValueError,
        TypeError,
        KeyError,
    ) as failure:
        flow.log.error(
            "oauth.failed",
            code="unexpected",
            attempt=listener.attempt.id,
            account=listener.attempt.account_id,
            error=type(failure).__name__,
        )
        flow.attempts.set_state(
            listener.attempt.id, AttemptState.FAILED, "oauth_failed"
        )
        listener.stop.set()
        respond(
            handler,
            500,
            "Connection failed",
            "downcroc hit an unexpected error. Return and try again.",
            "oauth_failed",
        )
        return
    except Exception as failure:  # noqa: BLE001 - never leave the browser hanging
        flow.log.error(
            "oauth.failed",
            code="unexpected",
            attempt=listener.attempt.id,
            account=listener.attempt.account_id,
            error=type(failure).__name__,
        )
        flow.attempts.set_state(
            listener.attempt.id, AttemptState.FAILED, "oauth_failed"
        )
        listener.stop.set()
        respond(
            handler,
            500,
            "Connection failed",
            "downcroc hit an unexpected error. Return and try again.",
            "oauth_failed",
        )
        return
    flow.attempts.set_state(listener.attempt.id, AttemptState.SUCCEEDED)
    listener.stop.set()
    respond(
        handler,
        200,
        "Mailbox connected",
        "You can close this window and return to downcroc.",
    )


def fail(flow: CallbackFlow, listener: Listener, code: str) -> None:
    flow.attempts.set_state(listener.attempt.id, AttemptState.FAILED, code)
    flow.log.warning(
        "oauth.failed",
        code=code,
        attempt=listener.attempt.id,
        account=listener.attempt.account_id,
    )
    listener.stop.set()


def respond(
    handler: BaseHTTPRequestHandler,
    status: int,
    title: str,
    message: str,
    code: str | None = None,
) -> None:
    detail = f"<p><code>{html.escape(code)}</code></p>" if code else ""
    body = PAGE.format(
        title=html.escape(title),
        message=html.escape(message),
        detail=detail,
    ).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Referrer-Policy", "no-referrer")
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.end_headers()
    handler.wfile.write(body)


def first(query: dict[str, list[str]], key: str) -> str:
    values = query.get(key)
    return values[0] if values else ""


def error_code(value: str) -> str:
    return value if ERROR_CODE.fullmatch(value) else "oauth_failed"


def elapsed_ms(started_at: str) -> int:
    try:
        elapsed = parse_utc(utc_now()) - parse_utc(started_at)
    except ValueError:
        return 0
    return max(0, round(elapsed.total_seconds() * 1000))
