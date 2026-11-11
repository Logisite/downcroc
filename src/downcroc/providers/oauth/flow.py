from __future__ import annotations

import secrets
import threading
import time

from sqlalchemy.exc import SQLAlchemyError

from downcroc.domain.accounts import Account
from downcroc.domain.attempts import AttemptKind, AttemptState, ConnectAttempt
from downcroc.domain.errors import (
    AttemptNotPending,
    AttemptPending,
    OAuthListenerFailed,
    OAuthNotConfigured,
    ProviderAuthMismatch,
)
from downcroc.domain.providers import AuthKind, ProviderSpec
from downcroc.providers.oauth import client as oauth_client
from downcroc.providers.oauth import events as oauth_events
from downcroc.providers.oauth import pkce
from downcroc.providers.oauth.callback import (
    CALLBACK_PATH,
    CallbackServer,
    Listener,
    OnCode,
)
from downcroc.runtime.clock import parse_utc, utc_after, utc_now
from downcroc.runtime.config.schema import ConnectSettings
from downcroc.runtime.ids import new_id
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.repositories.attempts import AttemptRepo


class OAuthFlow:
    def __init__(
        self,
        attempts: AttemptRepo,
        settings: ConnectSettings,
        log: EventLogger,
        on_code: OnCode,
    ) -> None:
        self.attempts = attempts
        self.log = log
        self.on_code = on_code
        self._settings = settings
        self._start_lock = threading.Lock()
        self._listeners_lock = threading.Lock()
        self._listeners: dict[str, Listener] = {}

    def start(self, account: Account, spec: ProviderSpec) -> ConnectAttempt:
        if spec.auth_kind is not AuthKind.OAUTH2:
            raise ProviderAuthMismatch(
                "this provider does not use oauth",
                hint="connect it with an app password",
            )
        if not spec.oauth_configured:
            raise OAuthNotConfigured(
                "the provider has no oauth client id",
                hint="run downcroc provider credentials set gmail --client PATH",
            )
        with self._start_lock:
            pending = self.attempts.pending_for_account(account.id)
            if pending is not None and self._expired(pending):
                self._expire(pending, "expired")
                self._stop(pending.id)
                pending = None
            if pending is not None:
                raise AttemptPending(
                    "an attempt is already waiting for this account",
                    hint=f"cancel attempt {pending.id} first",
                )
            return self._start(account, spec)

    @staticmethod
    def _expired(attempt: ConnectAttempt) -> bool:
        try:
            return parse_utc(utc_now()) >= parse_utc(attempt.expires_at)
        except ValueError:
            return True

    def _expire(self, attempt: ConnectAttempt, reason: str) -> None:
        if self.attempts.set_state(attempt.id, AttemptState.EXPIRED, reason):
            oauth_events.expired(self.log, attempt, reason)

    def _start(self, account: Account, spec: ProviderSpec) -> ConnectAttempt:
        try:
            server = CallbackServer(("127.0.0.1", 0))
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
                hint="run downcroc provider credentials set gmail --client PATH",
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
        listener = Listener(
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
            self.attempts.create(attempt)
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
            self.attempts.set_state(
                attempt.id, AttemptState.FAILED, "oauth_listener_failed"
            )
            server.server_close()
            with self._listeners_lock:
                self._listeners.pop(attempt.id, None)
            raise OAuthListenerFailed("the callback listener could not start") from None
        self.log.info(
            "oauth.started",
            provider=spec.id,
            account=account.id,
            attempt=attempt.id,
        )
        return attempt

    def get(self, attempt_id: str) -> ConnectAttempt:
        return self.attempts.get(attempt_id)

    def cancel(self, attempt_id: str) -> ConnectAttempt:
        attempt = self.attempts.get(attempt_id)
        if attempt.state is not AttemptState.PENDING:
            raise AttemptNotPending(
                "the attempt is already finished",
                hint="start a new attempt instead",
            )
        if not self.attempts.set_state(attempt_id, AttemptState.CANCELLED):
            raise AttemptNotPending(
                "the attempt is already finished",
                hint="start a new attempt instead",
            )
        self._stop(attempt_id)
        oauth_events.cancelled(self.log, attempt, "user")
        return self.attempts.get(attempt_id)

    def stop_for_account(self, account_id: str) -> None:
        with self._listeners_lock:
            attempts = [
                listener.attempt.id
                for listener in self._listeners.values()
                if listener.attempt.account_id == account_id
            ]
        for attempt_id in attempts:
            attempt = self.attempts.get(attempt_id)
            self.attempts.set_state(attempt_id, AttemptState.CANCELLED)
            self._stop(attempt_id)
            oauth_events.cancelled(self.log, attempt, "account_stop")

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
            self.attempts.set_state(listener.attempt.id, AttemptState.EXPIRED, reason)
            oauth_events.cancelled(self.log, listener.attempt, reason)

    def _serve(self, listener: Listener) -> None:
        expired = False
        try:
            while not listener.stop.is_set():
                if parse_utc(utc_now()) >= parse_utc(listener.attempt.expires_at):
                    expired = True
                    break
                listener.server.handle_request()
        except (OSError, ValueError, SQLAlchemyError) as failure:
            self.attempts.set_state(
                listener.attempt.id, AttemptState.FAILED, "oauth_failed"
            )
            self.log.error(
                "oauth.failed",
                code="listener_error",
                attempt=listener.attempt.id,
                account=listener.attempt.account_id,
                error=type(failure).__name__,
            )
        except Exception as failure:  # noqa: BLE001 - the listener must never die
            self.attempts.set_state(
                listener.attempt.id, AttemptState.FAILED, "oauth_failed"
            )
            self.log.error(
                "oauth.failed",
                code="listener_error",
                attempt=listener.attempt.id,
                account=listener.attempt.account_id,
                error=type(failure).__name__,
            )
        finally:
            if expired:
                self.attempts.set_state(
                    listener.attempt.id, AttemptState.EXPIRED, "expired"
                )
                oauth_events.expired(self.log, listener.attempt, "expired")
            listener.server.server_close()
            with self._listeners_lock:
                self._listeners.pop(listener.attempt.id, None)

    def _stop(self, attempt_id: str) -> None:
        with self._listeners_lock:
            listener = self._listeners.get(attempt_id)
        if listener is not None:
            listener.stop.set()
