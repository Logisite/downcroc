from __future__ import annotations

import email
import socketserver
import threading
from dataclasses import dataclass, field
from email.message import Message

from .imap_fake import _ImapHandler
from .mail_objects import _Mailbox, _Threaded


class _SmtpHandler(socketserver.StreamRequestHandler):
    def _send(self, text: str) -> None:
        self.wfile.write((text + "\r\n").encode())
        self.wfile.flush()

    def handle(self) -> None:
        self._send("220 localhost ESMTP downcroc-test")
        while True:
            line = self.rfile.readline()
            if not line:
                return
            text = line.decode("utf-8", "replace").rstrip("\r\n")
            upper = text.upper()
            if upper.startswith(("EHLO", "HELO")):
                self._send("250-localhost")
                self._send("250-AUTH PLAIN XOAUTH2")
                self._send("250-8BITMIME")
                self._send("250 OK")
            elif upper.startswith("AUTH "):
                self._auth(text)
            elif upper.startswith("MAIL FROM:"):
                self._send("250 2.1.0 OK")
            elif upper.startswith("RCPT TO:"):
                failure = self.server.owner.rcpt_failure(text)  # type: ignore[attr-defined]
                if failure is None:
                    self._send("250 2.1.5 OK")
                else:
                    self._send(failure)
            elif upper == "DATA":
                self._data()
            elif upper == "QUIT":
                self._send("221 2.0.0 Bye")
                return
            else:
                self._send("250 2.0.0 OK")

    def _auth(self, text: str) -> None:
        if self.server.owner.smtp_auth_rejected():  # type: ignore[attr-defined]
            self._send("535 5.7.8 authentication failed")
            return
        parts = text.split()
        if len(parts) == 2:
            self._send("334 ")
            self.rfile.readline()
        self._send("235 2.7.0 Accepted")

    def _data(self) -> None:
        self._send("354 End data with <CR><LF>.<CR><LF>")
        chunks: list[bytes] = []
        while True:
            line = self.rfile.readline()
            if not line or line in (b".\r\n", b".\n"):
                break
            if line.startswith(b".."):
                line = line[1:]
            chunks.append(line)
        self.server.owner.record(b"".join(chunks))  # type: ignore[attr-defined]
        self._send("250 2.0.0 queued")


@dataclass
class FakeMailServers:
    host: str = "127.0.0.1"
    smtp_port: int = 0
    imap_port: int = 0
    _messages: list[bytes] = field(default_factory=list)
    _sent_ids: set[str] = field(default_factory=set)
    _rcpt_counts: dict[str, int] = field(default_factory=dict)
    _inboxes: dict[str, _Mailbox] = field(default_factory=dict)
    _sent_boxes: dict[str, _Mailbox] = field(default_factory=dict)
    _gm_extensions: bool = True
    _rejected: set[str] = field(default_factory=set)
    _smtp_responses: dict[str, str] = field(default_factory=dict)
    _smtp_auth_rejected: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _smtp: _Threaded | None = None
    _imap: _Threaded | None = None

    def start(self) -> FakeMailServers:
        self._smtp = _Threaded((self.host, 0), _SmtpHandler)
        self._smtp.owner = self  # type: ignore[attr-defined]
        self._imap = _Threaded((self.host, 0), _ImapHandler)
        self._imap.owner = self  # type: ignore[attr-defined]
        self.smtp_port = self._smtp.server_address[1]
        self.imap_port = self._imap.server_address[1]
        threading.Thread(target=self._smtp.serve_forever, daemon=True).start()
        threading.Thread(target=self._imap.serve_forever, daemon=True).start()
        return self

    def stop(self) -> None:
        for server in (self._smtp, self._imap):
            if server is not None:
                server.shutdown()
                server.server_close()

    def record(self, raw: bytes) -> None:
        parsed = email.message_from_bytes(raw)
        message_id = (parsed.get("Message-ID") or "").strip().strip("<>")
        with self._lock:
            self._messages.append(raw)
            if message_id:
                self._sent_ids.add(message_id)

    def mailbox(self, address: str) -> _Mailbox:
        key = address.strip().lower()
        with self._lock:
            return self._inboxes.setdefault(key, _Mailbox())

    def deliver(self, address: str, raw: bytes) -> int:
        with self._lock:
            box = self._inboxes.setdefault(address.strip().lower(), _Mailbox())
            uid = box.uidnext
            box.uidnext += 1
            box.messages.append((uid, raw))
            return uid

    def deliver_sent(self, address: str, raw: bytes, thrid: int) -> int:
        with self._lock:
            box = self._sent_boxes.setdefault(address.strip().lower(), _Mailbox())
            uid = box.uidnext
            box.uidnext += 1
            box.messages.append((uid, raw))
            box.thrids[uid] = thrid
            return uid

    def sent_mailbox(self, address: str) -> _Mailbox:
        key = address.strip().lower()
        with self._lock:
            return self._sent_boxes.setdefault(key, _Mailbox())

    def delete_sent(self, address: str, message_id: str) -> bool:
        wanted = message_id.strip().strip("<>").encode()
        with self._lock:
            box = self._sent_boxes.get(address.strip().lower())
            if box is None:
                return False
            for uid, raw in list(box.messages):
                if wanted in raw:
                    box.messages.remove((uid, raw))
                    box.thrids.pop(uid, None)
                    return True
            return False

    def set_gm_extensions(self, enabled: bool) -> None:
        with self._lock:
            self._gm_extensions = enabled

    def gm_extensions_enabled(self) -> bool:
        with self._lock:
            return self._gm_extensions

    def inbox(self, address: str) -> list[tuple[int, bytes]]:
        with self._lock:
            box = self._inboxes.get(address.strip().lower())
            return list(box.messages) if box is not None else []

    def has_sent(self, message_id: str) -> bool:
        key = message_id.strip().strip("<>")
        with self._lock:
            return key in self._sent_ids

    def login_rejected(self, address: str) -> bool:
        with self._lock:
            return address.strip().lower() in self._rejected

    def reject_login(self, address: str) -> None:
        with self._lock:
            self._rejected.add(address.strip().lower())

    def smtp_response(self, address: str, response: str) -> None:
        with self._lock:
            self._smtp_responses[address.strip().lower()] = response

    def reject_smtp_auth(self) -> None:
        with self._lock:
            self._smtp_auth_rejected = True

    def smtp_auth_rejected(self) -> bool:
        with self._lock:
            return self._smtp_auth_rejected

    def rcpt_failure(self, line: str) -> str | None:
        address = line.split(":", 1)[-1].strip().strip("<>")
        local = address.split("@", 1)[0].lower()
        with self._lock:
            mapped = self._smtp_responses.get(address.lower())
            if mapped is not None:
                return mapped
            count = self._rcpt_counts.get(local, 0) + 1
            self._rcpt_counts[local] = count
        if "permanent" in local:
            if "once" in local and count > 1:
                return None
            return "550 5.1.1 no such user"
        if "transient" in local:
            if "once" in local and count > 1:
                return None
            return "451 4.3.0 try later"
        if "secondfails" in local and count == 2:
            return "550 5.1.1 no such user"
        return None

    def sent(self) -> list[Message]:
        with self._lock:
            raw = list(self._messages)
        return [email.message_from_bytes(item) for item in raw]

    def sent_ids(self) -> list[str]:
        with self._lock:
            return list(self._sent_ids)

    def reset(self) -> None:
        with self._lock:
            self._messages.clear()
            self._sent_ids.clear()
            self._rcpt_counts.clear()
            self._inboxes.clear()
            self._sent_boxes.clear()
            self._gm_extensions = True
            self._rejected.clear()
            self._smtp_responses.clear()
            self._smtp_auth_rejected = False

    @property
    def providers_toml(self) -> str:
        return (
            "[providers.generic]\n"
            f'imap_host = "{self.host}"\n'
            f"imap_port = {self.imap_port}\n"
            'imap_tls = "none"\n'
            f'smtp_host = "{self.host}"\n'
            f"smtp_port = {self.smtp_port}\n"
            'smtp_tls = "none"\n'
            'auth_kind = "app_password"\n'
            'smtp_auth_mechanism = "PLAIN"\n'
            'sent_folder = "Sent"\n'
            "supports_idle = false\n"
            "requires_user_agent = false\n"
            "attachment_max_bytes = 26214400\n"
        )
