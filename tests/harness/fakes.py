from __future__ import annotations

import email
import socketserver
import threading
from dataclasses import dataclass, field
from email.message import Message


class _Threaded(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


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
                self._send("250 2.1.5 OK")
            elif upper == "DATA":
                self._data()
            elif upper == "QUIT":
                self._send("221 2.0.0 Bye")
                return
            else:
                self._send("250 2.0.0 OK")

    def _auth(self, text: str) -> None:
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


class _ImapHandler(socketserver.StreamRequestHandler):
    def _send(self, text: str) -> None:
        self.wfile.write((text + "\r\n").encode())
        self.wfile.flush()

    def handle(self) -> None:
        self._send("* OK [CAPABILITY IMAP4rev1 AUTH=PLAIN] local ready")
        while True:
            line = self.rfile.readline()
            if not line:
                return
            text = line.decode("utf-8", "replace").rstrip("\r\n")
            if not text:
                continue
            parts = text.split(" ", 2)
            if len(parts) < 2:
                continue
            tag, command = parts[0], parts[1].upper()
            argument = parts[2] if len(parts) > 2 else ""
            if command == "CAPABILITY":
                self._send("* CAPABILITY IMAP4rev1 AUTH=PLAIN")
                self._send(f"{tag} OK CAPABILITY completed")
            elif command == "LOGIN":
                self._send(f"{tag} OK LOGIN completed")
            elif command == "AUTHENTICATE":
                self._send("+ ")
                self.rfile.readline()
                self._send(f"{tag} OK AUTHENTICATE completed")
            elif command == "NAMESPACE":
                self._send('* NAMESPACE (("" "/")) NIL NIL')
                self._send(f"{tag} OK NAMESPACE completed")
            elif command == "LIST":
                self._send('* LIST (\\HasNoChildren) "/" "INBOX"')
                self._send('* LIST (\\HasNoChildren) "/" "Sent"')
                self._send(f"{tag} OK LIST completed")
            elif command in ("SELECT", "EXAMINE"):
                self._send("* FLAGS (\\Seen)")
                self._send("* 0 EXISTS")
                self._send("* OK [UIDVALIDITY 100] UIDs valid")
                self._send("* OK [UIDNEXT 1] next")
                self._send(f"{tag} OK [READ-ONLY] {command} completed")
            elif command == "STATUS":
                self._send("* STATUS INBOX (UIDVALIDITY 100 UIDNEXT 1 MESSAGES 0)")
                self._send(f"{tag} OK STATUS completed")
            elif command == "UID":
                if argument.upper().startswith("SEARCH"):
                    self._send("* SEARCH")
                self._send(f"{tag} OK UID completed")
            elif command == "IDLE":
                self._send("+ idling")
                while True:
                    line = self.rfile.readline()
                    if not line or line.strip().upper() == b"DONE":
                        break
                self._send(f"{tag} OK IDLE completed")
            elif command in ("CLOSE", "UNSELECT", "NOOP"):
                self._send(f"{tag} OK {command} completed")
            elif command == "LOGOUT":
                self._send("* BYE logging out")
                self._send(f"{tag} OK LOGOUT completed")
                return
            else:
                self._send(f"{tag} OK {command} completed")


@dataclass
class FakeMailServers:
    host: str = "127.0.0.1"
    smtp_port: int = 0
    imap_port: int = 0
    _messages: list[bytes] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _smtp: _Threaded | None = None
    _imap: _Threaded | None = None

    def start(self) -> FakeMailServers:
        self._smtp = _Threaded((self.host, 0), _SmtpHandler)
        self._smtp.owner = self  # type: ignore[attr-defined]
        self._imap = _Threaded((self.host, 0), _ImapHandler)
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
        with self._lock:
            self._messages.append(raw)

    def sent(self) -> list[Message]:
        with self._lock:
            raw = list(self._messages)
        return [email.message_from_bytes(item) for item in raw]

    def reset(self) -> None:
        with self._lock:
            self._messages.clear()

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
