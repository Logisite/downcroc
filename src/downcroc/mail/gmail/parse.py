from __future__ import annotations

import hashlib

from imap_tools import MailMessage

from downcroc.domain.messages import IncomingMessage
from downcroc.mail.imap.parse import parse_message


def parse_raw(
    raw: bytes,
    provider_id: str,
    body_max_bytes: int,
) -> IncomingMessage:
    """Parse a Gmail ``messages.get?format=raw`` body.

    Gmail has no IMAP UID. A stable negative uid keeps the same message on the
    same row across sweeps while ``provider_id`` carries the real identity.
    """
    message = MailMessage.from_bytes(raw)
    return parse_message(
        message,
        0,
        body_max_bytes,
        uid=synthetic_uid(provider_id),
        provider_id=provider_id,
    )


def synthetic_uid(provider_id: str) -> int:
    digest = hashlib.sha1(provider_id.encode("utf-8")).hexdigest()[:8]
    return -(int(digest, 16) + 1)
