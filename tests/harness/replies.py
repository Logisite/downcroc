from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from email.utils import format_datetime

from tests.conftest import Stack
from tests.harness.fakes import FakeMailServers
from tests.harness.seed import until


def account_address(stack: Stack, account_id: str) -> str:
    return stack.api.get(f"/api/accounts/{account_id}")["address"]


def recipient_job(batch: dict, recipient: str) -> dict:
    return next(job for job in batch["recipients"] if job["recipient"] == recipient)


def reply_raw(
    *,
    to_address: str,
    from_address: str,
    subject: str,
    message_id: str | None = None,
    in_reply_to: str | None = None,
    references: tuple[str, ...] = (),
    date: datetime | None = None,
    text: str = "A reply",
) -> bytes:
    message = EmailMessage()
    message["From"] = f"Sender <{from_address}>"
    message["To"] = to_address
    message["Subject"] = subject
    message["Message-ID"] = f"<{message_id or uuid.uuid4().hex}@example.com>"
    if in_reply_to is not None:
        message["In-Reply-To"] = f"<{in_reply_to.strip('<>')}>"
    if references:
        message["References"] = " ".join(f"<{item.strip('<>')}>" for item in references)
    message["Date"] = format_datetime(date or datetime.now(UTC))
    message.set_content(text)
    return message.as_bytes()


def deliver_reply(
    fakes: FakeMailServers,
    *,
    to_address: str,
    from_address: str,
    subject: str,
    message_id: str | None = None,
    in_reply_to: str | None = None,
    references: tuple[str, ...] = (),
    date: datetime | None = None,
    text: str = "A reply",
) -> int:
    raw = reply_raw(
        to_address=to_address,
        from_address=from_address,
        subject=subject,
        message_id=message_id,
        in_reply_to=in_reply_to,
        references=references,
        date=date,
        text=text,
    )
    return fakes.deliver(to_address, raw)


def deliver_dsn(
    fakes: FakeMailServers,
    *,
    to_address: str,
    recipient: str,
    original_message_id: str | None = None,
    status: str = "5.1.1",
    action: str = "failed",
) -> int:
    boundary = f"dsn-{uuid.uuid4().hex}"
    stamp = format_datetime(datetime.now(UTC))
    raw = (
        "From: Mail Delivery System <mailer-daemon@local.test>\r\n"
        f"To: {to_address}\r\n"
        "Subject: Delivery Status Notification (Failure)\r\n"
        f"Message-ID: <{uuid.uuid4().hex}@local.test>\r\n"
        f"Date: {stamp}\r\n"
        "MIME-Version: 1.0\r\n"
        "Return-Path: <>\r\n"
        f"Content-Type: multipart/report; report-type=delivery-status; "
        f'boundary="{boundary}"\r\n'
        "\r\n"
        f"--{boundary}\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n"
        "\r\n"
        "The message could not be delivered.\r\n"
        f"--{boundary}\r\n"
        "Content-Type: message/delivery-status\r\n"
        "\r\n"
        "Reporting-MTA: dns; mx.local.test\r\n"
        f"Arrival-Date: {stamp}\r\n"
        "\r\n"
        f"Final-Recipient: rfc822; {recipient}\r\n"
        f"Action: {action}\r\n"
        f"Status: {status}\r\n"
        + (
            f"Original-Message-ID: <{original_message_id.strip('<>')}>\r\n"
            if original_message_id
            else ""
        )
        + "\r\n"
        f"--{boundary}--\r\n"
    ).encode()
    return fakes.deliver(to_address, raw)


def sync_and_wait(
    stack: Stack, account_id: str, expected: int, timeout: float = 20.0
) -> list[dict]:
    stack.api.post(f"/api/accounts/{account_id}/sync")
    until(
        lambda: len(messages(stack, account_id)) >= expected,
        timeout=timeout,
    )
    return messages(stack, account_id)


def messages(stack: Stack, account_id: str) -> list[dict]:
    return stack.api.get(f"/api/messages?account={account_id}&limit=500")


def at_offset(days: int) -> datetime:
    return datetime.now(UTC) + timedelta(days=days)
