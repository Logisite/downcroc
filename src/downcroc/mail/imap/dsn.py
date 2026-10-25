from __future__ import annotations

from dataclasses import dataclass
from email.message import Message
from email.utils import parseaddr

from downcroc.domain.messages import normalize_message_id


@dataclass(frozen=True)
class DsnInfo:
    is_dsn: bool
    action: str | None = None
    code: str | None = None
    recipient: str | None = None
    original_message_id: str | None = None


def classify_dsn(root: Message) -> DsnInfo:
    delivery_part = any(
        part.get_content_type() == "message/delivery-status" for part in root.walk()
    )
    multipart_report = root.get_content_type() == "multipart/report"
    report_type = str(root.get_param("report-type") or "").lower()
    sender = parseaddr(str(root.get("From") or ""))[1].lower()
    automated = sender.startswith(("mailer-daemon@", "postmaster@"))
    return_path = str(root.get("Return-Path") or "").strip()
    is_dsn = (
        delivery_part
        or (multipart_report and report_type == "delivery-status")
        or (multipart_report and automated)
        or return_path == "<>"
    )
    if not is_dsn:
        return DsnInfo(is_dsn=False)
    return DsnInfo(
        is_dsn=True,
        action=_field(root, "Action"),
        code=_field(root, "Status"),
        recipient=_address(_field(root, "Final-Recipient")),
        original_message_id=normalize_message_id(_field(root, "Original-Message-ID")),
    )


def _field(root: Message, name: str) -> str | None:
    for part in root.walk():
        value = part.get(name)
        if value:
            return str(value).strip()
    return None


def _address(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.rsplit(";", 1)[-1].strip()
    address = parseaddr(candidate)[1] or candidate
    address = address.strip().strip("<>").lower()
    return address or None
