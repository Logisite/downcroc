from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Query, Request, Response

from downcroc.api.schemas.messages import (
    MessageOut,
    MessageSummaryOut,
    ThreadDetailOut,
    ThreadOut,
)
from downcroc.core.bootstrap import Services
from downcroc.store.content import safe_filename

router = APIRouter(tags=["mail"])


def _services(request: Request) -> Services:
    return request.app.state.services


@router.get("/api/messages", response_model=list[MessageSummaryOut])
def list_messages(
    request: Request,
    response: Response,
    account: str | None = None,
    folder: str | None = None,
    thread: str | None = None,
    reply_state: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[MessageSummaryOut]:
    repo = _services(request).messages
    messages = repo.list_messages(
        account_id=account,
        folder=folder,
        thread_id=thread,
        reply_state=reply_state,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )
    response.headers["X-Total-Count"] = str(
        repo.count_messages(
            account_id=account,
            folder=folder,
            thread_id=thread,
            reply_state=reply_state,
            since=since,
            until=until,
        )
    )
    return [MessageSummaryOut.of(message) for message in messages]


@router.get("/api/messages/{message_id}", response_model=MessageOut)
def get_message(message_id: str, request: Request) -> MessageOut:
    return MessageOut.of(_services(request).messages.get_message(message_id))


@router.get("/api/messages/{message_id}/attachments/{attachment_id}")
def download_attachment(
    message_id: str, attachment_id: str, request: Request
) -> Response:
    services = _services(request)
    attachment = services.messages.get_attachment(message_id, attachment_id)
    payload = services.content.read(attachment.path, attachment.hash)
    fallback = safe_filename(attachment.filename, "attachment")
    disposition = (
        f'attachment; filename="{fallback}"; '
        f"filename*=UTF-8''{quote(attachment.filename, safe='')}"
    )
    return Response(
        content=payload,
        media_type=attachment.content_type or "application/octet-stream",
        headers={"Content-Disposition": disposition},
    )


@router.get("/api/threads", response_model=list[ThreadOut])
def list_threads(
    request: Request,
    response: Response,
    account: str | None = None,
    batch: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[ThreadOut]:
    repo = _services(request).messages
    threads = repo.list_threads(
        account_id=account,
        batch_id=batch,
        limit=limit,
        offset=offset,
    )
    response.headers["X-Total-Count"] = str(
        repo.count_threads(account_id=account, batch_id=batch)
    )
    return [ThreadOut.of(thread) for thread in threads]


@router.get("/api/threads/{thread_id}", response_model=ThreadDetailOut)
def get_thread(thread_id: str, request: Request) -> ThreadDetailOut:
    thread, messages = _services(request).messages.get_thread(thread_id)
    return ThreadDetailOut(
        thread=ThreadOut.of(thread),
        messages=[MessageSummaryOut.of(message) for message in messages],
    )
