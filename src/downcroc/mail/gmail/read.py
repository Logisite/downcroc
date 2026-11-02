from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from downcroc.domain.providers import ProviderSpec
from downcroc.mail.gmail import api

HISTORY_PATH = "/gmail/v1/users/me/history"
MESSAGES_PATH = "/gmail/v1/users/me/messages"


@dataclass(frozen=True)
class GmailMessageRef:
    id: str
    thread_id: str | None


@dataclass(frozen=True)
class GmailHistoryPage:
    history_id: str | None
    messages: tuple[GmailMessageRef, ...]
    next_page_token: str | None


@dataclass(frozen=True)
class GmailListPage:
    messages: tuple[GmailMessageRef, ...]
    next_page_token: str | None
    result_size_estimate: int


@dataclass(frozen=True)
class GmailMessage:
    id: str
    thread_id: str | None
    label_ids: tuple[str, ...]
    raw: bytes | None
    message_id_header: str | None
    size: int
    internal_date_ms: int


def history(
    spec: ProviderSpec,
    access_token: str,
    start_history_id: str,
    *,
    timeout_s: float,
    page_token: str | None = None,
    label_id: str | None = None,
    project_id: str | None = None,
) -> GmailHistoryPage:
    _require_api(spec)
    params: dict[str, Any] = {
        "startHistoryId": start_history_id,
        "historyTypes": "messageAdded",
    }
    if page_token:
        params["pageToken"] = page_token
    if label_id:
        params["labelId"] = label_id
    response = api._request(
        spec,
        "GET",
        HISTORY_PATH,
        access_token,
        timeout_s,
        params=params,
        project_id=project_id,
        history=True,
    )
    payload = api._json(response, project_id)
    refs: dict[str, GmailMessageRef] = {}
    for record in _records(payload.get("history")):
        for added in _records(record.get("messagesAdded")):
            message = added.get("message")
            if not isinstance(message, dict):
                continue
            message_id = _text(message.get("id"))
            if message_id is None:
                continue
            refs[message_id] = GmailMessageRef(
                id=message_id,
                thread_id=_text(message.get("threadId")),
            )
    return GmailHistoryPage(
        history_id=_text(payload.get("historyId")),
        messages=tuple(refs.values()),
        next_page_token=_text(payload.get("nextPageToken")),
    )


def list_messages(
    spec: ProviderSpec,
    access_token: str,
    query: str,
    *,
    timeout_s: float,
    page_token: str | None = None,
    max_results: int = 100,
    project_id: str | None = None,
) -> GmailListPage:
    _require_api(spec)
    params: dict[str, Any] = {"q": query, "maxResults": max(1, max_results)}
    if page_token:
        params["pageToken"] = page_token
    response = api._request(
        spec,
        "GET",
        MESSAGES_PATH,
        access_token,
        timeout_s,
        params=params,
        project_id=project_id,
    )
    payload = api._json(response, project_id)
    refs: list[GmailMessageRef] = []
    for item in _records(payload.get("messages")):
        message_id = _text(item.get("id"))
        if message_id is None:
            continue
        refs.append(
            GmailMessageRef(
                id=message_id,
                thread_id=_text(item.get("threadId")),
            )
        )
    estimate = payload.get("resultSizeEstimate")
    return GmailListPage(
        messages=tuple(refs),
        next_page_token=_text(payload.get("nextPageToken")),
        result_size_estimate=estimate
        if isinstance(estimate, int) and not isinstance(estimate, bool)
        else 0,
    )


def backfill_refs(
    spec: ProviderSpec,
    access_token: str,
    *,
    days: int,
    limit: int,
    timeout_s: float,
    project_id: str | None = None,
    stop: object | None = None,
) -> tuple[GmailMessageRef, ...]:
    since = _days_ago(days)
    stamp = since.strftime("%Y/%m/%d") if since is not None else None
    refs: dict[str, GmailMessageRef] = {}
    for label in ("in:inbox", "in:sent"):
        query = label if stamp is None else f"{label} after:{stamp}"
        page: str | None = None
        while len(refs) < limit:
            remaining = limit - len(refs)
            found = list_messages(
                spec,
                access_token,
                query,
                timeout_s=timeout_s,
                page_token=page,
                max_results=min(100, remaining),
                project_id=project_id,
            )
            for ref in found.messages:
                refs.setdefault(ref.id, ref)
            page = found.next_page_token
            if page is None or (
                stop is not None and getattr(stop, "is_set", lambda: False)()
            ):
                break
    return tuple(refs.values())


def get_message(
    spec: ProviderSpec,
    access_token: str,
    message_id: str,
    *,
    timeout_s: float,
    fmt: str = "raw",
    metadata_headers: tuple[str, ...] = (),
    project_id: str | None = None,
) -> GmailMessage:
    _require_api(spec)
    params: dict[str, Any] = {"format": fmt}
    if metadata_headers:
        params["metadataHeaders"] = list(metadata_headers)
    response = api._request(
        spec,
        "GET",
        f"{MESSAGES_PATH}/{message_id}",
        access_token,
        timeout_s,
        params=params,
        project_id=project_id,
    )
    payload = api._json(response, project_id)
    labels = payload.get("labelIds")
    label_ids = (
        tuple(item for item in labels if isinstance(item, str))
        if isinstance(labels, list)
        else ()
    )
    raw_value = payload.get("raw")
    raw = _decode(raw_value) if isinstance(raw_value, str) else None
    size = payload.get("sizeEstimate")
    internal = payload.get("internalDate")
    return GmailMessage(
        id=_text(payload.get("id")) or message_id,
        thread_id=_text(payload.get("threadId")),
        label_ids=label_ids,
        raw=raw,
        message_id_header=_header(payload) or _raw_header(raw),
        size=size if isinstance(size, int) and not isinstance(size, bool) else 0,
        internal_date_ms=(
            int(internal)
            if isinstance(internal, (str, int))
            and not isinstance(internal, bool)
            and str(internal).isdigit()
            else 0
        ),
    )


def _header(payload: dict[str, Any]) -> str | None:
    body = payload.get("payload")
    if not isinstance(body, dict):
        return None
    headers = body.get("headers")
    if not isinstance(headers, list):
        return None
    for item in headers:
        if not isinstance(item, dict):
            continue
        if str(item.get("name", "")).lower() != "message-id":
            continue
        value = _text(item.get("value"))
        if value:
            return value
    return None


def _raw_header(raw: bytes | None) -> str | None:
    if not raw:
        return None
    from email.parser import BytesHeaderParser

    parsed = BytesHeaderParser().parsebytes(raw)
    return _text(parsed.get("Message-ID"))


def _decode(value: str) -> bytes | None:
    text = value.strip().replace("-", "+").replace("_", "/")
    text += "=" * (-len(text) % 4)
    try:
        return base64.b64decode(text)
    except ValueError, TypeError:
        return None


def _records(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _days_ago(days: int) -> datetime | None:
    if days <= 0:
        return None
    return datetime.now(UTC) - timedelta(days=days)


def _require_api(spec: ProviderSpec) -> None:
    if not spec.api_configured:
        raise api.GmailApiFailure(
            "gmail_api_not_configured",
            "the provider has no gmail api base url",
        )
