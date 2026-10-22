from __future__ import annotations

import hmac
import html
import re
import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from sqlalchemy.exc import SQLAlchemyError

from downcroc.domain.accounts import Account
from downcroc.domain.attempts import AttemptKind, AttemptState, ConnectAttempt
from downcroc.domain.errors import (
    AttemptNotPending,
    AttemptPending,
    DomainError,
    OAuthListenerFailed,
    OAuthNotConfigured,
    ProviderAuthMismatch,
)
from downcroc.domain.providers import AuthKind, ProviderSpec
from downcroc.providers.oauth import client as oauth_client
from downcroc.providers.oauth import pkce
from downcroc.runtime.clock import parse_utc, utc_after, utc_now
from downcroc.runtime.config.schema import ConnectSettings
from downcroc.runtime.ids import new_id
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


@dataclass
class _Listener:
    attempt: ConnectAttempt
    spec: ProviderSpec
    redirect_uri: str
    verifier: str
    server: HTTPServer
    stop: threading.Event
    flow: OAuthFlow
    thread: threading.Thread | None = None


class _CallbackServer(HTTPServer):
    owner: _Listener
    allow_reuse_address = False

    def __init__(self, server_address: tuple[str, int]) -> None:
        super().__init__(server_address, _CallbackHandler)
        self.timeout = POLL_SECONDS


class _CallbackHandler(BaseHTTPRequestHandler):
    server: _CallbackServer

    def do_GET(self) -> None:
        self.server.owner.flow.handle(self.server.owner, self)

    def log_message(self, format: str, *args: Any) -> None:
        return


class OAuthFlow:
    def __init__(
        self,
        attempts: AttemptRepo,
        settings: ConnectSettings,
        log: EventLogger,
        on_code: OnCode,
    ) -> None:
        self._attempts = attempts
        self._settings = settings
        self._log = log
        self._on_code = on_code
        self._start_lock = threading.Lock()
        self._listeners_lock = threading.Lock()
        self._listeners: dict[str, _Listener] = {}

    def start(self, account: Account, spec: ProviderSpec) -> ConnectAttempt:
        if spec.auth_kind is not AuthKind.OAUTH2:
            raise ProviderAuthMismatch(
                "this provider does not use oauth",
                hint="connect it with an app password",
            )
        if not spec.oauth_configured:
            raise OAuthNotConfigured(
                "the provider has no oauth client id",
                hint="set oauth_client_id in providers.toml",
            )
        with self._start_lock:
            pending = self._attempts.pending_for_account(account.id)
            if pending is not None:
                raise AttemptPending(
                    "an attempt is already waiting for this account",
                    hint=f"cancel attempt {pending.id} first",
                )
            return self._start(account, spec)

    def _start(self, account: Account, spec: ProviderSpec) -> ConnectAttempt:
        try:
            server = _CallbackServer(("127.0.0.1", 0))
        except OSError as error:
            raise OAuthListenerFailed(
                "the callback listener could not start",
                hint="check that loopback sockets are available",
            ) from error
        port = server.server_address[1]
        redirect_uri = f"http://127.0.0.1:{port}{CALLBACK_PATH}"
        state_token = secrets.token_urlsafe(32)
        verifier = pkce.new_verifier()
        try:
            url = oauth_client.authorization_url(
                spec, redirect_uri, state_token, pkce.challenge(verifier)
            )
        except oauth_client.OAuthError as error:
            server.server_close()
            raise OAuthNotConfigured(
                "the provider has no oauth client id",
                hint="set oauth_client_id in providers.toml",
            ) from error
        attempt = ConnectAttempt(
            id=new_id("att"),
            account_id=account.id,
            kind=AttemptKind.OAUTH,
            state=AttemptState.PENDING,
            authorization_url=url,
            state_token=state_token,
            callback_port=port,
            created_at=utc_now(),
            expires_at=utc_after(self._settings.oauth_attempt_ttl_s),
            error=None,
        )
        listener = _Listener(
            attempt=attempt,
            spec=spec,
            redirect_uri=redirect_uri,
            verifier=verifier,
            server=server,
            stop=threading.Event(),
            flow=self,
        )
        server.owner = listener
        try:
            self._attempts.create(attempt)
        except Exception:
            server.server_close()
            raise
        listener.thread = threading.Thread(
            target=self._serve,
            args=(listener,),
            name=f"oauth-{attempt.id}",
            daemon=True,
        )
        with self._listeners_lock:
            self._listeners[attempt.id] = listener
        try:
            listener.thread.start()
        except RuntimeError:
            self._attempts.set_state(
                attempt.id, AttemptState.FAILED, "oauth_listener_failed"
            )
            server.server_close()
            with self._listeners_lock:
                self._listeners.pop(attempt.id, None)
            raise OAuthListenerFailed("the callback listener could not start") from None
        self._log.info(
            "oauth.started",
            provider=spec.id,
            account=account.id,
            attempt=attempt.id,
        )
        return attempt

    def get(self, attempt_id: str) -> ConnectAttempt:
        return self._attempts.get(attempt_id)

    def cancel(self, attempt_id: str) -> ConnectAttempt:
        attempt = self._attempts.get(attempt_id)
        if attempt.state is not AttemptState.PENDING:
            raise AttemptNotPending(
                "the attempt is already finished",
                hint="start a new attempt instead",
            )
        if not self._attempts.set_state(attempt_id, AttemptState.CANCELLED):
            raise AttemptNotPending(
                "the attempt is already finished",
                hint="start a new attempt instead",
            )
        self._stop(attempt_id)
        return self._attempts.get(attempt_id)

    def stop_for_account(self, account_id: str) -> None:
        with self._listeners_lock:
            attempts = [
                listener.attempt.id
                for listener in self._listeners.values()
                if listener.attempt.account_id == account_id
            ]
        for attempt_id in attempts:
            self._attempts.set_state(attempt_id, AttemptState.CANCELLED)
            self._stop(attempt_id)

    def close_all(self, reason: str) -> None:
        with self._listeners_lock:
            listeners = list(self._listeners.values())
        for listener in listeners:
            listener.stop.set()
        deadline = time.monotonic() + self._settings.shutdown_join_s
        for listener in listeners:
            if listener.thread is not None:
                remaining = max(0.0, deadline - time.monotonic())
                listener.thread.join(remaining)
        for listener in listeners:
            self._attempts.set_state(listener.attempt.id, AttemptState.EXPIRED, reason)

    def handle(self, listener: _Listener, handler: BaseHTTPRequestHandler) -> None:
        parsed = urlparse(handler.path)
        if parsed.path != CALLBACK_PATH:
            self._respond(handler, 404, "Not found", "This is not a callback path.")
            return
        query = parse_qs(parsed.query, keep_blank_values=True)
        state = _first(query, "state")
        state_ok = hmac.compare_digest(state, listener.attempt.state_token)
        self._log.info(
            "oauth.callback",
            state_ok=state_ok,
            elapsed_ms=_elapsed_ms(listener.attempt.created_at),
            attempt=listener.attempt.id,
            account=listener.attempt.account_id,
        )
        if not state_ok:
            self._respond(
                handler,
                400,
                "Callback rejected",
                "This callback does not match a pending connect attempt.",
            )
            return
        current = self._attempts.get(listener.attempt.id)
        if current.state is not AttemptState.PENDING:
            self._respond(
                handler,
                409,
                "Attempt finished",
                "This connect attempt has already finished.",
            )
            return
        if parse_utc(utc_now()) >= parse_utc(listener.attempt.expires_at):
            self._attempts.set_state(
                listener.attempt.id, AttemptState.EXPIRED, "expired"
            )
            self._log.warning(
                "oauth.failed",
                code="expired",
                attempt=listener.attempt.id,
                account=listener.attempt.account_id,
            )
            listener.stop.set()
            self._respond(
                handler,
                410,
                "Attempt expired",
                "This connect attempt expired. Start a new one.",
                "expired",
            )
            return
        error = _first(query, "error")
        if error:
            code = _error_code(error)
            self._attempts.set_state(listener.attempt.id, AttemptState.FAILED, code)
            self._log.warning(
                "oauth.failed",
                code=code,
                attempt=listener.attempt.id,
                account=listener.attempt.account_id,
            )
            listener.stop.set()
            self._respond(
                handler,
                200,
                "Authorization not granted",
                "downcroc did not receive permission to connect the mailbox.",
                code,
            )
            return
        code = _first(query, "code")
        if not code:
            self._attempts.set_state(
                listener.attempt.id, AttemptState.FAILED, "oauth_no_code"
            )
            self._log.warning(
                "oauth.failed",
                code="oauth_no_code",
                attempt=listener.attempt.id,
                account=listener.attempt.account_id,
            )
            listener.stop.set()
            self._respond(
                handler,
                400,
                "Callback incomplete",
                "The provider did not return an authorization code.",
                "oauth_no_code",
            )
            return
        try:
            self._on_code(
                listener.attempt,
                listener.spec,
                code,
                listener.redirect_uri,
                listener.verifier,
            )
        except DomainError as failure:
            self._fail(listener, failure.code)
            self._respond(
                handler,
                502,
                "Connection failed",
                "downcroc could not verify the mailbox. Return and try again.",
                failure.code,
            )
            return
        except oauth_client.OAuthError as failure:
            self._fail(listener, failure.code)
            self._respond(
                handler,
                502,
                "Connection failed",
                "The provider rejected the authorization. Return and try again.",
                failure.code,
            )
            return
        except oauth_client.OAuthUnavailableError:
            self._fail(listener, "oauth_unavailable")
            self._respond(
                handler,
                502,
                "Provider unreachable",
                "The provider could not be reached. Return and try again.",
                "oauth_unavailable",
            )
            return
        except (SQLAlchemyError, OSError, RuntimeError) as failure:
            self._log.error(
                "oauth.failed",
                code="unexpected",
                attempt=listener.attempt.id,
                account=listener.attempt.account_id,
                error=type(failure).__name__,
            )
            self._attempts.set_state(
                listener.attempt.id, AttemptState.FAILED, "oauth_failed"
            )
            listener.stop.set()
            self._respond(
                handler,
                500,
                "Connection failed",
                "downcroc hit an unexpected error. Return and try again.",
                "oauth_failed",
            )
            return
        self._attempts.set_state(listener.attempt.id, AttemptState.SUCCEEDED)
        listener.stop.set()
        self._respond(
            handler,
            200,
            "Mailbox connected",
            "You can close this window and return to downcroc.",
        )

    def _fail(self, listener: _Listener, code: str) -> None:
        self._attempts.set_state(listener.attempt.id, AttemptState.FAILED, code)
        self._log.warning(
            "oauth.failed",
            code=code,
            attempt=listener.attempt.id,
            account=listener.attempt.account_id,
        )
        listener.stop.set()

    def _serve(self, listener: _Listener) -> None:
        expired = False
        try:
            while not listener.stop.is_set():
                if parse_utc(utc_now()) >= parse_utc(listener.attempt.expires_at):
                    expired = True
                    break
                listener.server.handle_request()
        except (OSError, ValueError, SQLAlchemyError) as failure:
            self._attempts.set_state(
                listener.attempt.id, AttemptState.FAILED, "oauth_failed"
            )
            self._log.error(
                "oauth.failed",
                code="listener_error",
                attempt=listener.attempt.id,
                account=listener.attempt.account_id,
                error=type(failure).__name__,
            )
        finally:
            if expired:
                self._attempts.set_state(
                    listener.attempt.id, AttemptState.EXPIRED, "expired"
                )
                self._log.warning(
                    "oauth.failed",
                    code="expired",
                    attempt=listener.attempt.id,
                    account=listener.attempt.account_id,
                )
            listener.server.server_close()
            with self._listeners_lock:
                self._listeners.pop(listener.attempt.id, None)

    def _stop(self, attempt_id: str) -> None:
        with self._listeners_lock:
            listener = self._listeners.get(attempt_id)
        if listener is not None:
            listener.stop.set()

    def _respond(
        self,
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


def _first(query: dict[str, list[str]], key: str) -> str:
    values = query.get(key)
    return values[0] if values else ""


def _error_code(value: str) -> str:
    return value if ERROR_CODE.fullmatch(value) else "oauth_failed"


def _elapsed_ms(started_at: str) -> int:
    try:
        elapsed = parse_utc(utc_now()) - parse_utc(started_at)
    except ValueError:
        return 0
    return max(0, round(elapsed.total_seconds() * 1000))
