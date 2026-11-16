from __future__ import annotations

import base64
import email
import re
import shlex
import socketserver

from .mail_objects import _crlf, _Mailbox

MESSAGE_ID = re.compile(r'HEADER\s+"?Message-ID"?\s+"?<?([^"\s>]+)', re.IGNORECASE)
XOAUTH2_USER = re.compile(r"user=([^\s\x00\x01]+)")


class _ImapHandler(socketserver.StreamRequestHandler):
    user = ""
    selected = "INBOX"

    def _send(self, text: str) -> None:
        self.wfile.write((text + "\r\n").encode())
        self.wfile.flush()

    def _box(self) -> _Mailbox:
        return self.server.owner.mailbox(self.user)  # type: ignore[attr-defined]

    def _selected_box(self) -> _Mailbox:
        if self.selected == "INBOX":
            return self._box()
        return self.server.owner.sent_mailbox(self.user)  # type: ignore[attr-defined]

    def _search(self, criteria: str) -> None:
        box = self._selected_box()
        uids = [uid for uid, _ in box.messages]
        criteria = re.sub(r"^CHARSET\s+\S+\s+", "", criteria, flags=re.IGNORECASE)
        ranged = re.search(r"UID\s+(\d+):(\*|\d+)", criteria, re.IGNORECASE)
        header = MESSAGE_ID.search(criteria)
        if ranged:
            start = int(ranged.group(1))
            end = None if ranged.group(2) == "*" else int(ranged.group(2))
            uids = [uid for uid in uids if uid >= start and (end is None or uid <= end)]
        elif header:
            wanted = header.group(1).strip().strip("<>") if header else ""
            uids = [
                uid for uid, raw in box.messages if wanted and wanted.encode() in raw
            ]
            known = (
                self.selected != "INBOX"
                and not uids
                and wanted
                and self.server.owner.has_sent(wanted)  # type: ignore[attr-defined]
            )
            if known:
                # Pre-mirroring behaviour: SMTP-only sent mail is known.
                uids = [1]
        self._send("* SEARCH" + (" " + " ".join(map(str, uids)) if uids else ""))

    def _fetch(self, argument: str) -> None:
        token = argument.split(" ", 1)[0]
        items = argument.split(" ", 1)[1] if " " in argument else ""
        wanted = self._uids(token)
        box = self._selected_box()
        messages = dict(box.messages)
        gm = "X-GM-THRID" in items.upper()
        for uid in wanted:
            raw = messages.get(uid)
            if raw is None:
                continue
            raw = _crlf(raw)
            if gm:
                self._fetch_gm(uid, raw, box.thrids.get(uid, uid))
                continue
            self.wfile.write(
                (
                    f"* {uid} FETCH (UID {uid} FLAGS (\\Seen) "
                    f"RFC822.SIZE {len(raw)} BODY[] {{{len(raw)}}}\r\n"
                ).encode()
            )
            self.wfile.write(raw)
            self.wfile.write(b")\r\n")
            self.wfile.flush()

    @staticmethod
    def _uids(token: str) -> list[int]:
        wanted: list[int] = []
        for part in token.split(","):
            start, _, end = part.partition(":")
            if start.isdigit():
                stop = int(start) if not end.isdigit() else int(end)
                wanted.extend(range(int(start), stop + 1))
        return wanted

    def _fetch_gm(self, uid: int, raw: bytes, thrid: int) -> None:
        parsed = email.message_from_bytes(raw)
        header = f"Message-ID: {parsed.get('Message-ID') or ''}\r\n".encode()
        self.wfile.write(
            (
                f"* {uid} FETCH (UID {uid} X-GM-THRID {thrid} "
                f"BODY[HEADER.FIELDS (MESSAGE-ID)] {{{len(header)}}}\r\n"
            ).encode()
        )
        self.wfile.write(header)
        self.wfile.write(b")\r\n")
        self.wfile.flush()

    def handle(self) -> None:
        caps = "IMAP4rev1 AUTH=PLAIN"
        if self.server.owner.gm_extensions_enabled():  # type: ignore[attr-defined]
            caps += " SPECIAL-USE X-GM-EXT-1"
        self._send(f"* OK [CAPABILITY {caps}] local ready")
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
                self._send(f"* CAPABILITY {caps}")
                self._send(f"{tag} OK CAPABILITY completed")
            elif command == "LOGIN":
                arguments = shlex.split(argument)
                self.user = arguments[0].lower() if arguments else ""
                if self.server.owner.login_rejected(self.user):  # type: ignore[attr-defined]
                    self._send(f"{tag} NO [AUTHENTICATIONFAILED] invalid credentials")
                    continue
                self._send(f"{tag} OK LOGIN completed")
            elif command == "AUTHENTICATE":
                mechanism, _, initial = argument.partition(" ")
                if initial:
                    # SASL initial response: the payload came with the command.
                    self.user = _xoauth2_user(initial.encode()) or self.user
                else:
                    self._send("+ ")
                    payload = self.rfile.readline().strip()
                    if mechanism.upper() == "XOAUTH2":
                        self.user = _xoauth2_user(payload) or self.user
                if self.server.owner.login_rejected(self.user):  # type: ignore[attr-defined]
                    self._send(f"{tag} NO [AUTHENTICATIONFAILED] invalid credentials")
                    continue
                self._send(f"{tag} OK AUTHENTICATE completed")
            elif command == "NAMESPACE":
                self._send('* NAMESPACE (("" "/")) NIL NIL')
                self._send(f"{tag} OK NAMESPACE completed")
            elif command == "LIST":
                sent_flag = (
                    " \\Sent" if self.server.owner.gm_extensions_enabled() else ""
                )  # type: ignore[attr-defined]
                self._send('* LIST (\\HasNoChildren) "/" "INBOX"')
                self._send(f'* LIST (\\HasNoChildren{sent_flag}) "/" "Sent"')
                self._send(f"{tag} OK LIST completed")
            elif command in ("SELECT", "EXAMINE"):
                self.selected = _folder(argument).upper()
                box = self._selected_box()
                count = len(box.messages)
                self._send("* FLAGS (\\Seen)")
                self._send(f"* {count} EXISTS")
                self._send(f"* OK [UIDVALIDITY {box.uidvalidity}] UIDs valid")
                self._send(f"* OK [UIDNEXT {box.uidnext}] next")
                mode = "READ-ONLY" if command == "EXAMINE" else "READ-WRITE"
                self._send(f"{tag} OK [{mode}] {command} completed")
            elif command == "STATUS":
                folder = _folder(argument)
                box = self._selected_box() if folder.upper() != "INBOX" else self._box()
                values = (
                    f"UIDVALIDITY {box.uidvalidity} "
                    f"UIDNEXT {box.uidnext} MESSAGES {len(box.messages)}"
                )
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


def _folder(argument: str) -> str:
    parts = shlex.split(argument)
    return parts[0] if parts else "INBOX"


def _xoauth2_user(payload: bytes) -> str | None:
    padded = payload + b"=" * (-len(payload) % 4)
    try:
        decoded = base64.b64decode(padded).decode("utf-8", "replace")
    except ValueError, TypeError:
        return None
    match = XOAUTH2_USER.search(decoded)
    return match.group(1).lower() if match else None
