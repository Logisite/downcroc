from __future__ import annotations

import email
import re
import shlex
import socketserver
import threading
from dataclasses import dataclass, field
from email.message import Message

MESSAGE_ID = re.compile(r'HEADER\s+"?Message-ID"?\s+"?<?([^"\s>]+)', re.IGNORECASE)


class _Threaded(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


@dataclass
class _Mailbox:
    uidvalidity: int = 100
    uidnext: int = 1
    messages: list[tuple[int, bytes]] = field(default_factory=list)


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
    user = ""
    selected = "INBOX"

    def _send(self, text: str) -> None:
        self.wfile.write((text + "\r\n").encode())
        self.wfile.flush()

    def _box(self) -> _Mailbox:
        return self.server.owner.mailbox(self.user)  # type: ignore[attr-defined]

    def _search(self, criteria: str) -> None:
        if self.selected != "INBOX":
            match = MESSAGE_ID.search(criteria)
            found = bool(
                match and self.server.owner.has_sent(match.group(1))  # type: ignore[attr-defined]
            )
            self._send("* SEARCH 1" if found else "* SEARCH")
            return
        box = self._box()
        uids = [uid for uid, _ in box.messages]
        ranged = re.search(r"UID\s+(\d+):(\*|\d+)", criteria, re.IGNORECASE)
        if ranged:
            start = int(ranged.group(1))
            end = None if ranged.group(2) == "*" else int(ranged.group(2))
            uids = [uid for uid in uids if uid >= start and (end is None or uid <= end)]
        elif "HEADER" in criteria.upper():
            match = MESSAGE_ID.search(criteria)
            wanted = match.group(1).strip().strip("<>") if match else ""
            uids = [
                uid for uid, raw in box.messages if wanted and wanted.encode() in raw
            ]
        self._send("* SEARCH" + (" " + " ".join(map(str, uids)) if uids else ""))

    def _fetch(self, argument: str) -> None:
        token = argument.split(" ", 1)[0]
        wanted = [int(item) for item in token.split(",") if item.isdigit()]
        box = self._box()
        messages = dict(box.messages)
        for uid in wanted:
            raw = messages.get(uid)
            if raw is None:
                continue
            raw = _crlf(raw)
            self.wfile.write(
                (
                    f"* {uid} FETCH (UID {uid} FLAGS (\\Seen) "
                    f"RFC822.SIZE {len(raw)} BODY[] {{{len(raw)}}}\r\n"
                ).encode()
            )
            self.wfile.write(raw)
            self.wfile.write(b")\r\n")
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
                arguments = shlex.split(argument)
                self.user = arguments[0].lower() if arguments else ""
                if self.server.owner.login_rejected(self.user):  # type: ignore[attr-defined]
                    self._send(f"{tag} NO [AUTHENTICATIONFAILED] invalid credentials")
                    continue
                self._send(f"{tag} OK LOGIN completed")
            elif command == "AUTHENTICATE":
                self._send("+ ")
                self.rfile.readline()
                if self.server.owner.login_rejected(self.user):  # type: ignore[attr-defined]
                    self._send(f"{tag} NO [AUTHENTICATIONFAILED] invalid credentials")
                    continue
                self._send(f"{tag} OK AUTHENTICATE completed")
            elif command == "NAMESPACE":
                self._send('* NAMESPACE (("" "/")) NIL NIL')
                self._send(f"{tag} OK NAMESPACE completed")
            elif command == "LIST":
                self._send('* LIST (\\HasNoChildren) "/" "INBOX"')
                self._send('* LIST (\\HasNoChildren) "/" "Sent"')
                self._send(f"{tag} OK LIST completed")
            elif command in ("SELECT", "EXAMINE"):
                self.selected = _folder(argument).upper()
                box = self._box()
                count = 0 if self.selected != "INBOX" else len(box.messages)
                uidnext = 1 if self.selected != "INBOX" else box.uidnext
                uidvalidity = 1 if self.selected != "INBOX" else box.uidvalidity
                self._send("* FLAGS (\\Seen)")
                self._send(f"* {count} EXISTS")
                self._send(f"* OK [UIDVALIDITY {uidvalidity}] UIDs valid")
                self._send(f"* OK [UIDNEXT {uidnext}] next")
                mode = "READ-ONLY" if command == "EXAMINE" else "READ-WRITE"
                self._send(f"{tag} OK [{mode}] {command} completed")
            elif command == "STATUS":
                folder = _folder(argument)
                box = self._box()
                if folder.upper() == "INBOX":
                    values = (
                        f"UIDVALIDITY {box.uidvalidity} "
                        f"UIDNEXT {box.uidnext} MESSAGES {len(box.messages)}"
                    )
                else:
                    values = "UIDVALIDITY 1 UIDNEXT 1 MESSAGES 0"
                self._send(f"* STATUS {folder} ({values})")
                self._send(f"{tag} OK STATUS completed")
            elif command == "UID":
                subcommand, _, rest = argument.partition(" ")
                if subcommand.upper() == "SEARCH":
                    self._search(rest)
                elif subcommand.upper() == "FETCH":
                    self._fetch(rest)
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
    _sent_ids: set[str] = field(default_factory=set)
    _rcpt_counts: dict[str, int] = field(default_factory=dict)
    _inboxes: dict[str, _Mailbox] = field(default_factory=dict)
    _rejected: set[str] = field(default_factory=set)
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

    def rcpt_failure(self, line: str) -> str | None:
        address = line.split(":", 1)[-1].strip().strip("<>")
        local = address.split("@", 1)[0].lower()
        with self._lock:
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
            self._rejected.clear()

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


def _folder(argument: str) -> str:
    parts = shlex.split(argument)
    return parts[0] if parts else "INBOX"


def _crlf(raw: bytes) -> bytes:
    normalized = raw.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    return normalized if normalized.endswith(b"\r\n") else normalized + b"\r\n"
