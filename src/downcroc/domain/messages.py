from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class IncomingAttachment:
    filename: str
    content_type: str
    payload: bytes
    inline: bool
    content_id: str | None


@dataclass(frozen=True)
class IncomingMessage:
    uid: int
    uidvalidity: int
    message_id: str | None
    in_reply_to: str | None
    references: tuple[str, ...]
    subject: str
    from_address: str
    from_name: str
    to: tuple[str, ...]
    date: str
    size: int
    body_text: str | None
    body_html: str | None
    body_truncated: bool
    attachments: tuple[IncomingAttachment, ...]
    is_dsn: bool = False
    is_auto_reply: bool = False
    dsn_status: str | None = None
    dsn_code: str | None = None
    dsn_recipient: str | None = None
    dsn_original_message_id: str | None = None
    provider_id: str | None = None


@dataclass(frozen=True)
class Attachment:
    id: str
    message_id: str
    filename: str
    content_type: str
    size: int
    path: str
    hash: str
    inline: bool
    content_id: str | None


@dataclass(frozen=True)
class PreparedAttachment:
    id: str
    filename: str
    content_type: str
    size: int
    path: str
    hash: str
    inline: bool
    content_id: str | None


@dataclass(frozen=True)
class Message:
    id: str
    account_id: str
    folder: str
    uid: int
    uidvalidity: int
    message_id: str | None
    in_reply_to: str | None
    references: tuple[str, ...]
    subject: str
    from_address: str
    from_name: str
    to: tuple[str, ...]
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
    attachments: tuple[Attachment, ...] = ()


@dataclass(frozen=True)
class MessageSummary:
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


@dataclass(frozen=True)
class Thread:
    id: str
    root_message_id: str
    subject: str
    batch_id: str | None
    message_count: int
    reply_count: int
    first_seen: str
    last_seen: str


_ID = re.compile(r"<([^<>]+)>")
_REPLY_TOKENS = frozenset(
    {
        "re",
        "fwd",
        "fw",
        "aw",
        "sv",
        "vs",
        "antw",
        "antwort",
        "res",
        "rif",
        "enc",
        "wg",
        "odp",
        "tr",
        "ynt",
    }
)
_AUTO_PHRASES = (
    "out of office",
    "out-of-office",
    "automatic reply",
    "auto reply",
    "auto-reply",
    "autoreply",
    "autoresponse",
    "auto response",
    "vacation",
    "abwesenheit",
    "risposta automatica",
    "réponse automatique",
    "resposta automática",
    "automatische antwort",
    "automatisk svar",
)
_CJK_TOKENS = ("回复", "答复", "返信", "转发", "轉寄")


def normalize_message_id(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if cleaned.startswith("<") and cleaned.endswith(">"):
        cleaned = cleaned[1:-1]
    cleaned = cleaned.strip()
    return cleaned or None


def parse_references(*values: str | None) -> tuple[str, ...]:
    found: list[str] = []
    for value in values:
        if not value:
            continue
        matches = _ID.findall(value)
        if not matches:
            matches = value.split()
        for match in matches:
            cleaned = normalize_message_id(match)
            if cleaned is not None and cleaned not in found:
                found.append(cleaned)
    return tuple(found)


def _strip_one_prefix(value: str) -> tuple[str, bool]:
    text = value.lstrip()
    if text.startswith("["):
        end = text.find("]")
        if 0 < end <= 41:
            text = text[end + 1 :].lstrip()
    lowered = text.casefold()
    for phrase in _AUTO_PHRASES:
        if lowered.startswith(phrase):
            return text[len(phrase) :].lstrip(" :-"), True
    for token in _CJK_TOKENS:
        if text.startswith(token):
            return text[len(token) :].lstrip(" :："), True
    head, separator, rest = _prefix_head(text)
    if separator and head.casefold() in _REPLY_TOKENS:
        return rest.lstrip(), True
    return text, False


def _prefix_head(text: str) -> tuple[str, str, str]:
    for index, character in enumerate(text):
        if character in ":：-":
            head = text[:index].strip()
            if head.endswith("]") and "[" in head:
                head = head[: head.rfind("[")].strip()
            return head, character, text[index + 1 :]
        if character.isspace() and index > 16:
            break
    return text, "", ""


def _strip_reply_prefixes(value: str) -> str:
    current = value
    for _ in range(8):
        updated, changed = _strip_one_prefix(current)
        if not changed:
            break
        current = updated
    return current


def normalize_subject(value: str) -> str:
    stripped = _strip_reply_prefixes(value or "")
    return " ".join(stripped.lower().split())


def has_reply_prefix(value: str) -> bool:
    return _strip_reply_prefixes(value or "") != (value or "").lstrip()
