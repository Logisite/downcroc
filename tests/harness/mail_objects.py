from __future__ import annotations

import socketserver
from dataclasses import dataclass, field


class _Threaded(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


@dataclass
class _Mailbox:
    uidvalidity: int = 100
    uidnext: int = 1
    messages: list[tuple[int, bytes]] = field(default_factory=list)
    thrids: dict[int, int] = field(default_factory=dict)


def _crlf(raw: bytes) -> bytes:
    normalized = raw.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    return normalized if normalized.endswith(b"\r\n") else normalized + b"\r\n"
