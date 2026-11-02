from __future__ import annotations

import base64
import json
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .fakes import FakeMailServers

API = "/gmail/v1/users/me"


@dataclass
class FakeMessage:
    id: str
    raw: bytes
    labels: tuple[str, ...]
    history_id: int

    @property
    def message_id(self) -> str | None:
        header = b"Message-ID: "
        for line in self.raw.splitlines():
            if line.lower().startswith(header.lower()):
                return line[len(header) :].decode().strip().strip("<>")
        return None


@dataclass
class FakeGmail:
    host: str = "127.0.0.1"
    _messages: list[FakeMessage] = field(default_factory=list)
    _history: int = 100
    _expired_before: int | None = None
    _server: ThreadingHTTPServer | None = None
    _thread: threading.Thread | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def port(self) -> int:
        return int(self._server.server_address[1])

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def start(self) -> FakeGmail:
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                owner._get(self)

            def do_POST(self) -> None:
                owner._post(self)

            def log_message(self, *args: object) -> None:
                return

        self._server = ThreadingHTTPServer((self.host, 0), Handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
        )
        self._thread.start()
        return self

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()

    def add(
        self,
        raw: bytes,
        *,
        labels: tuple[str, ...] = ("INBOX",),
    ) -> str:
        with self._lock:
            self._history += 1
            message = FakeMessage(
                id=f"gm{len(self._messages) + 1}",
                raw=raw,
                labels=labels,
                history_id=self._history,
            )
            self._messages.append(message)
            return message.id

    def expire_history(self) -> None:
        with self._lock:
            self._expired_before = self._history + 1

    def reset_expiry(self) -> None:
        with self._lock:
            self._expired_before = None

    def history_id(self) -> int:
        with self._lock:
            return self._history

    def _get(self, handler: BaseHTTPRequestHandler) -> None:
        parsed = urlparse(handler.path)
        query = parse_qs(parsed.query)
        if parsed.path == f"{API}/profile":
            with self._lock:
                payload = {
                    "emailAddress": "gmail@local.test",
                    "messagesTotal": len(self._messages),
                    "threadsTotal": len(self._messages),
                    "historyId": str(self._history),
                }
            self._json(handler, 200, payload)
            return
        if parsed.path == f"{API}/history":
            self._history_page(handler, query)
            return
        if parsed.path == f"{API}/messages":
            self._list(handler, query)
            return
        if parsed.path.startswith(f"{API}/messages/"):
            self._message(handler, parsed.path.rsplit("/", 1)[-1], query)
            return
        self._json(handler, 404, {"error": {"message": "not found"}})

    def _history_page(
        self,
        handler: BaseHTTPRequestHandler,
        query: dict[str, list[str]],
    ) -> None:
        start = int(query.get("startHistoryId", ["0"])[0])
        label = query.get("labelId", [None])[0]
        with self._lock:
            if self._expired_before is not None and start < self._expired_before:
                self._json(
                    handler,
                    404,
                    {"error": {"message": "startHistoryId is too old"}},
                )
                return
            records = []
            for message in self._messages:
                if message.history_id <= start:
                    continue
                if label is not None and label not in message.labels:
                    continue
                records.append(
                    {
                        "id": str(message.history_id),
                        "messagesAdded": [
                            {
                                "message": {
                                    "id": message.id,
                                    "threadId": message.id,
                                    "labelIds": list(message.labels),
                                }
                            }
                        ],
                    }
                )
            payload = {
                "history": records,
                "historyId": str(self._history),
            }
        self._json(handler, 200, payload)

    def _list(
        self,
        handler: BaseHTTPRequestHandler,
        query: dict[str, list[str]],
    ) -> None:
        text = query.get("q", [""])[0]
        excluded = {"SPAM", "TRASH"} if "in:spam" in text else set()
        labels = None
        if "in:inbox" in text:
            labels = {"INBOX"}
        elif "in:sent" in text:
            labels = {"SENT"}
        with self._lock:
            messages = [
                {
                    "id": message.id,
                    "threadId": message.id,
                }
                for message in self._messages
                if (labels is None or labels & set(message.labels))
                and not (excluded & set(message.labels))
            ]
        self._json(
            handler,
            200,
            {"messages": messages, "resultSizeEstimate": len(messages)},
        )

    def _message(
        self,
        handler: BaseHTTPRequestHandler,
        message_id: str,
        query: dict[str, list[str]],
    ) -> None:
        with self._lock:
            message = next(
                (item for item in self._messages if item.id == message_id),
                None,
            )
        if message is None:
            self._json(handler, 404, {"error": {"message": "missing"}})
            return
        fmt = query.get("format", ["full"])[0]
        payload: dict[str, object] = {
            "id": message.id,
            "threadId": message.id,
            "labelIds": list(message.labels),
            "sizeEstimate": len(message.raw),
            "internalDate": "0",
        }
        if fmt == "metadata":
            payload["payload"] = {
                "headers": [{"name": "Message-ID", "value": message.message_id or ""}]
            }
        else:
            payload["raw"] = base64.urlsafe_b64encode(message.raw).decode().rstrip("=")
        self._json(handler, 200, payload)

    def _post(self, handler: BaseHTTPRequestHandler) -> None:
        parsed = urlparse(handler.path)
        length = int(handler.headers.get("Content-Length", "0"))
        handler.rfile.read(length)
        if parsed.path == "/token":
            self._json(
                handler,
                200,
                {
                    "access_token": "access-token",
                    "refresh_token": "refresh-token",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                    "scope": "https://mail.google.com/",
                },
            )
            return
        self._json(handler, 404, {"error": {"message": "not found"}})

    @staticmethod
    def _json(
        handler: BaseHTTPRequestHandler,
        status: int,
        payload: dict[str, object],
    ) -> None:
        body = json.dumps(payload).encode()
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)

    def provider_toml(self, fakes: FakeMailServers, *, client: bool = True) -> str:
        builtin = (
            'oauth_client_id = "test-client"\noauth_client_secret = "test-secret"\n'
            if client
            else ""
        )
        return (
            "[providers.gmail]\n"
            'label = "Gmail (fake)"\n'
            f'imap_host = "{fakes.host}"\n'
            f"imap_port = {fakes.imap_port}\n"
            'imap_tls = "none"\n'
            f'smtp_host = "{fakes.host}"\n'
            f"smtp_port = {fakes.smtp_port}\n"
            'smtp_tls = "none"\n'
            'auth_kind = "oauth2"\n'
            'smtp_auth_mechanism = "XOAUTH2"\n'
            'sent_folder = "Sent"\n'
            "supports_idle = false\n"
            "requires_user_agent = false\n"
            "attachment_max_bytes = 26214400\n"
            'transport = "gmail_api"\n'
            f'api_base_url = "{self.base_url}"\n'
            "api_max_concurrency = 2\n"
            "api_rate_per_min = 120\n"
            'oauth_scopes = ["https://mail.google.com/"]\n'
            'api_scopes = ["https://mail.google.com/"]\n'
            f'oauth_authorize_url = "{self.base_url}/authorize"\n'
            f'oauth_token_url = "{self.base_url}/token"\n'
            f"{builtin}"
        )
