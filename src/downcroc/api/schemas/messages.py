from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from downcroc.domain.messages import (
    Attachment,
    Message,
    MessageSummary,
    Thread,
)


class AttachmentOut(BaseModel):
    id: str
    filename: str
    content_type: str
    size: int
    hash: str
    inline: bool
    content_id: str | None

    @classmethod
    def of(cls, attachment: Attachment) -> AttachmentOut:
        return cls(
            id=attachment.id,
            filename=attachment.filename,
            content_type=attachment.content_type,
            size=attachment.size,
            hash=attachment.hash,
            inline=attachment.inline,
            content_id=attachment.content_id,
        )


class MessageSummaryOut(BaseModel):
    id: str
    account_id: str
    folder: str
    uid: int
    message_id: str | None
    subject: str
    from_address: str
    from_name: str
    date: str
    size: int
    is_dsn: bool
    reply_state: str
    thread_id: str | None
    job_id: str | None
    ingested_at: str
    attachment_count: int

    @classmethod
    def of(cls, message: MessageSummary) -> MessageSummaryOut:
        return cls(
            id=message.id,
            account_id=message.account_id,
            folder=message.folder,
            uid=message.uid,
            message_id=message.message_id,
            subject=message.subject,
            from_address=message.from_address,
            from_name=message.from_name,
            date=message.date,
            size=message.size,
            is_dsn=message.is_dsn,
            reply_state=message.reply_state,
            thread_id=message.thread_id,
            job_id=message.job_id,
            ingested_at=message.ingested_at,
            attachment_count=message.attachment_count,
        )


class MessageOut(BaseModel):
    id: str
    account_id: str
    folder: str
    uid: int
    uidvalidity: int
    message_id: str | None
    in_reply_to: str | None
    references: list[str]
    subject: str
    from_address: str
    from_name: str
    to: list[str]
    date: str
    size: int
    is_dsn: bool
    reply_state: str
    thread_id: str | None
    job_id: str | None
    body_text: str | None
    body_html: str | None
    body_truncated: bool
    ingested_at: str
    attachments: list[AttachmentOut]

    @classmethod
    def of(cls, message: Message) -> MessageOut:
        return cls(
            id=message.id,
            account_id=message.account_id,
            folder=message.folder,
            uid=message.uid,
            uidvalidity=message.uidvalidity,
            message_id=message.message_id,
            in_reply_to=message.in_reply_to,
            references=list(message.references),
            subject=message.subject,
            from_address=message.from_address,
            from_name=message.from_name,
            to=list(message.to),
            date=message.date,
            size=message.size,
            is_dsn=message.is_dsn,
            reply_state=message.reply_state,
            thread_id=message.thread_id,
            job_id=message.job_id,
            body_text=message.body_text,
            body_html=message.body_html,
            body_truncated=message.body_truncated,
            ingested_at=message.ingested_at,
            attachments=[
                AttachmentOut.of(attachment) for attachment in message.attachments
            ],
        )


class ThreadOut(BaseModel):
    id: str
    root_message_id: str
    subject: str
    batch_id: str | None
    message_count: int
    reply_count: int
    first_seen: str
    last_seen: str

    @classmethod
    def of(cls, thread: Thread) -> ThreadOut:
        return cls(
            id=thread.id,
            root_message_id=thread.root_message_id,
            subject=thread.subject,
            batch_id=thread.batch_id,
            message_count=thread.message_count,
            reply_count=thread.reply_count,
            first_seen=thread.first_seen,
            last_seen=thread.last_seen,
        )


class ThreadDetailOut(BaseModel):
    thread: ThreadOut
    messages: list[MessageSummaryOut]


class MailPruneRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str | None = None
    dry_run: bool = False
    confirm: bool = False


class MailPruneOut(BaseModel):
    messages: int
    bytes: int
    dry_run: bool
    account_id: str | None = None
