from __future__ import annotations

from datetime import UTC, datetime

from imap_tools import MailMessage

from downcroc.domain.messages import (
    IncomingAttachment,
    IncomingMessage,
    normalize_message_id,
    parse_references,
)
from downcroc.mail.imap.dsn import classify_dsn


def parse_message(
    message: MailMessage,
    uidvalidity: int,
    body_max_bytes: int,
) -> IncomingMessage:
    uid = int(message.uid or 0)
    in_reply_to = parse_references(message.obj.get("In-Reply-To"))
    references = parse_references(*message.obj.get_all("References", []))
    text, text_cut = _truncate(message.text, body_max_bytes)
    html, html_cut = _truncate(message.html, body_max_bytes)
    sender = message.from_values
    dsn = classify_dsn(message.obj)
    return IncomingMessage(
        uid=uid,
        uidvalidity=uidvalidity,
        message_id=normalize_message_id(message.obj.get("Message-ID")),
        in_reply_to=in_reply_to[0] if in_reply_to else None,
        references=references,
        subject=message.subject,
        from_address=(sender.email if sender else "").lower(),
        from_name=sender.name if sender else "",
        to=tuple(message.to),
        date=_date(message.date),
        size=message.size,
        body_text=text or None,
        body_html=html or None,
        body_truncated=text_cut or html_cut,
        attachments=tuple(
            IncomingAttachment(
                filename=item.filename or f"attachment-{index}",
                content_type=item.content_type,
                payload=item.payload,
                inline=item.content_disposition == "inline" or bool(item.content_id),
                content_id=item.content_id or None,
            )
            for index, item in enumerate(message.attachments, start=1)
        ),
        is_dsn=dsn.is_dsn,
        dsn_status=dsn.action,
        dsn_code=dsn.code,
        dsn_recipient=dsn.recipient,
        dsn_original_message_id=dsn.original_message_id,
    )


def _date(moment: datetime) -> str:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return (
        moment.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    )


def _truncate(value: str, limit: int) -> tuple[str, bool]:
    if not value:
        return "", False
    encoded = value.encode("utf-8")
    if len(encoded) <= limit:
        return value, False
    return encoded[:limit].decode("utf-8", errors="ignore"), True
