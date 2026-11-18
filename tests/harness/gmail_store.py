from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from email.parser import BytesParser
from email.utils import parseaddr

API = "/gmail/v1/users/me"
RFC822MSGID = re.compile(r"rfc822msgid:<?([^>\s]+)", re.IGNORECASE)


def _wire(payload: dict) -> bytes:
    raw = payload.get("raw")
    if not isinstance(raw, str) or not raw:
        return b""
    padded = raw + "=" * (-len(raw) % 4)
    try:
        return base64.urlsafe_b64decode(padded)
    except ValueError, TypeError:
        return b""


def _sender(raw: bytes) -> str:
    header = BytesParser().parsebytes(raw, headersonly=True).get("From")
    return parseaddr(header or "")[1].lower()


def overwrite_message_id(raw: bytes, delivered: str) -> bytes:
    """Replace the Message-ID header, simulating Gmail's send-time rewrite."""

    lines = raw.splitlines(keepends=True)
    out: list[bytes] = []
    replaced = False
    for line in lines:
        if line.lower().startswith(b"message-id:") and not replaced:
            out.append(f"Message-ID: <{delivered}>\r\n".encode())
            replaced = True
        else:
            out.append(line)
    return b"".join(out)


@dataclass
class FakeMessage:
    id: str
    raw: bytes
    labels: tuple[str, ...]
    history_id: int
    thread_id: str | None = None

    @property
    def thread(self) -> str:
        return self.thread_id or self.id

    @property
    def thrid(self) -> int:
        return int(self.thread, 16)

    @property
    def message_id(self) -> str | None:
        header = b"Message-ID: "
        for line in self.raw.splitlines():
            if line.lower().startswith(header.lower()):
                return line[len(header) :].decode().strip().strip("<>")
        return None
