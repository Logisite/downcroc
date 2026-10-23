from __future__ import annotations

import io
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.generator import BytesGenerator
from email.message import EmailMessage
from email.parser import BytesParser
from email.policy import SMTP
from email.utils import format_datetime, formataddr


@dataclass(frozen=True)
class OutgoingAttachment:
    filename: str
    content_type: str
    payload: bytes
    inline: bool = False
    content_id: str | None = None


def mint_message_id(address: str, exists: Callable[[str], bool]) -> str:
    domain = address.rsplit("@", 1)[-1].strip().lower() or "localhost"
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    for _ in range(16):
        candidate = f"{stamp}.{secrets.token_hex(6)}@{domain}"
        if not exists(candidate):
            return candidate
    raise RuntimeError("could not mint a unique message id")


def build_message(
    *,
    from_address: str,
    from_name: str,
    to_address: str,
    to_name: str | None,
    subject: str,
    text: str,
    html: str | None,
    message_id: str,
    reply_to: str | None = None,
    attachments: tuple[OutgoingAttachment, ...] = (),
) -> bytes:
    message = EmailMessage(policy=SMTP)
    _set_headers(
        message,
        from_address=from_address,
        from_name=from_name,
        to_address=to_address,
        to_name=to_name,
        subject=subject,
        message_id=message_id,
        reply_to=reply_to,
    )
    message.set_content(text, subtype="plain", charset="utf-8")
    if html:
        message.add_alternative(html, subtype="html", charset="utf-8")
    for attachment in attachments:
        maintype, _, subtype = attachment.content_type.partition("/")
        message.add_attachment(
            attachment.payload,
            maintype=maintype or "application",
            subtype=subtype or "octet-stream",
            filename=attachment.filename,
            disposition="inline" if attachment.inline else "attachment",
        )
    return _serialize(message)


def prepare_for_send(
    payload: bytes,
    *,
    from_address: str,
    from_name: str,
    to_address: str,
    to_name: str | None,
    subject: str,
    message_id: str,
    reply_to: str | None = None,
) -> bytes:
    message = BytesParser(policy=SMTP).parsebytes(payload)
    for name in ("From", "To", "Subject", "Date", "Message-ID", "Reply-To"):
        if name in message:
            del message[name]
    _set_headers(
        message,
        from_address=from_address,
        from_name=from_name,
        to_address=to_address,
        to_name=to_name,
        subject=subject,
        message_id=message_id,
        reply_to=reply_to,
    )
    return _serialize(message)


def _set_headers(
    message: EmailMessage,
    *,
    from_address: str,
    from_name: str,
    to_address: str,
    to_name: str | None,
    subject: str,
    message_id: str,
    reply_to: str | None,
) -> None:
    message["From"] = formataddr((from_name, from_address))
    message["To"] = formataddr((to_name or "", to_address))
    message["Subject"] = subject
    message["Date"] = format_datetime(datetime.now(UTC))
    message["Message-ID"] = _angle(message_id)
    if "MIME-Version" not in message:
        message["MIME-Version"] = "1.0"
    if reply_to:
        message["Reply-To"] = reply_to


def _serialize(message: EmailMessage) -> bytes:
    buffer = io.BytesIO()
    generator = BytesGenerator(buffer, policy=SMTP)
    generator.flatten(message, linesep="\r\n")
    return buffer.getvalue()


def _angle(message_id: str) -> str:
    cleaned = message_id.strip()
    if cleaned.startswith("<") and cleaned.endswith(">"):
        return cleaned
    return f"<{cleaned}>"
