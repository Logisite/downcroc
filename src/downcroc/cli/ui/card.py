from __future__ import annotations

import sys
import textwrap

from downcroc.cli.ui import ansi

MAX_WIDTH = 100
LABEL_WIDTH = 9
INDENT = 2

UNICODE = {
    "top_left": "\u256d",
    "top_right": "\u256e",
    "bottom_left": "\u2570",
    "bottom_right": "\u256f",
    "left": "\u2502",
    "right": "\u2502",
    "tee_left": "\u251c",
    "tee_right": "\u2524",
    "bar": "\u2500",
}

ASCII = {
    "top_left": "+",
    "top_right": "+",
    "bottom_left": "+",
    "bottom_right": "+",
    "left": "|",
    "right": "|",
    "tee_left": "+",
    "tee_right": "+",
    "bar": "-",
}


def message_card(ui: object, message: dict, limit: int) -> list[str]:
    box = _box()
    total = max(4, min(limit, MAX_WIDTH))
    inner = total - 2
    content = max(1, inner - 2)
    rows = [_edge(box, "top_left", "top_right", inner)]
    rows.append(_row(box, _key(ui, message), content))
    rows.append(_separator(box, inner))
    rows.extend(_field(ui, box, "subject", _subject(message), content))
    rows.append(_separator(box, inner))
    rows.extend(_field(ui, box, "to", _recipient(message), content))
    rows.append(_separator(box, inner))
    rows.extend(_body(ui, box, message, content))
    attachments = [_clean(name) for name in message.get("attachments") or []]
    if attachments:
        rows.append(_separator(box, inner))
        for name in attachments:
            rows.extend(_attachment(ui, box, name, content))
    rows.append(_edge(box, "bottom_left", "bottom_right", inner))
    return rows


def mail_card(ui: object, message: dict, limit: int) -> list[str]:
    box = _box()
    total = max(4, min(limit, MAX_WIDTH))
    inner = total - 2
    content = max(1, inner - 2)
    rows = [_edge(box, "top_left", "top_right", inner)]
    rows.append(_row(box, _mail_title(ui, message), content))
    rows.append(_separator(box, inner))
    rows.extend(_field(ui, box, "subject", _subject(message), content))
    rows.append(_separator(box, inner))
    rows.extend(_field(ui, box, "from", _mail_from(message), content))
    rows.extend(_field(ui, box, "to", _mail_to(message), content))
    rows.extend(
        _field(ui, box, "date", _clean(str(message.get("date") or "-")), content)
    )
    reply = _clean(str(message.get("reply_label") or _mail_reply(message)))
    if reply and reply != "-":
        rows.extend(_field(ui, box, "reply", reply, content))
    context = _mail_context(message)
    if context:
        rows.extend(_field(ui, box, "context", context, content))
    rows.append(_separator(box, inner))
    rows.extend(_mail_body(ui, box, message, content))
    attachments = message.get("attachments") or []
    if attachments:
        rows.append(_separator(box, inner))
        for item in attachments:
            rows.extend(_mail_attachment(ui, box, item, content))
    rows.append(_edge(box, "bottom_left", "bottom_right", inner))
    return rows


def _box() -> dict[str, str]:
    return UNICODE if _unicode_ready() else ASCII


def _unicode_ready() -> bool:
    encoding = (getattr(sys.stdout, "encoding", None) or "").casefold()
    return "utf" in encoding or encoding == "cp65001"


def _edge(box: dict[str, str], left: str, right: str, inner: int) -> str:
    return f"{box[left]}{box['bar'] * max(0, inner)}{box[right]}"


def _separator(box: dict[str, str], inner: int) -> str:
    return f"{box['tee_left']}{box['bar'] * max(0, inner)}{box['tee_right']}"


def _row(box: dict[str, str], text: str, content: int) -> str:
    body = ansi.fit(text, content)
    pad = max(0, content - ansi.cells(body))
    return f"{box['left']} {body}{' ' * pad} {box['right']}"


def _key(ui: object, message: dict) -> str:
    key = _clean(str(message.get("key") or "-"))
    return ui.bold(ui.accent(key))


def _subject(message: dict) -> str:
    subject = _clean(str(message.get("subject") or "")).strip()
    return subject or "(no subject)"


def _recipient(message: dict) -> str:
    email = _clean(str(message.get("email") or "")).strip()
    name = _clean(str(message.get("name") or "")).strip()
    if name and email:
        return f"{name} <{email}>"
    return email or name or "-"


def _field(
    ui: object, box: dict[str, str], label: str, value: str, content: int
) -> list[str]:
    if content < LABEL_WIDTH + 8:
        rows = [_row(box, ui.dim(label), content)]
        rows.extend(
            _row(box, " " * INDENT + line, content)
            for line in _wrap(value, content - INDENT)
        )
        return rows
    parts = _wrap(value, content - LABEL_WIDTH)
    prefix = f"{label:<{LABEL_WIDTH}}"
    rows = [_row(box, ui.dim(prefix) + parts[0], content)]
    rows.extend(_row(box, " " * LABEL_WIDTH + part, content) for part in parts[1:])
    return rows


def _body(ui: object, box: dict[str, str], message: dict, content: int) -> list[str]:
    rows = [_row(box, ui.dim("body"), content)]
    text = _clean(str(message.get("text") or ""))
    if not text.strip():
        note = "(html only)" if message.get("html") else "(empty)"
        rows.append(_row(box, " " * INDENT + ui.dim(note), content))
        return rows
    rows.extend(
        _row(box, " " * INDENT + line, content)
        for line in _wrap(text, content - INDENT)
    )
    return rows


def _mail_title(ui: object, message: dict) -> str:
    ident = _clean(str(message.get("id") or message.get("key") or "-"))
    return ui.bold(ui.accent(ident))


def _mail_from(message: dict) -> str:
    email = _clean(
        str(message.get("from_address") or message.get("email") or "")
    ).strip()
    name = _clean(str(message.get("from_name") or message.get("name") or "")).strip()
    if name and email:
        return f"{name} <{email}>"
    return email or name or "-"


def _mail_to(message: dict) -> str:
    value = message.get("to")
    if isinstance(value, list):
        items = [_clean(str(item)).strip() for item in value if str(item).strip()]
        return ", ".join(items) if items else "-"
    return _recipient(message)


def _mail_reply(message: dict) -> str:
    state = str(message.get("reply_state") or "")
    if state and state != "none":
        return state
    return "-"


def _mail_context(message: dict) -> str:
    parts: list[str] = []
    for label, key in (
        ("thread", "thread_id"),
        ("job", "job_id"),
        ("folder", "folder"),
        ("account", "account_id"),
    ):
        value = message.get(key)
        if value:
            parts.append(f"{label} {_clean(str(value))}")
    return ", ".join(parts)


def _mail_body(
    ui: object, box: dict[str, str], message: dict, content: int
) -> list[str]:
    rows = [_row(box, ui.dim("body"), content)]
    text = _clean(str(message.get("body_text") or message.get("text") or ""))
    if not text.strip():
        if message.get("body_html") or message.get("html"):
            note = "(html only)"
        else:
            note = "(empty)"
        rows.append(_row(box, " " * INDENT + ui.dim(note), content))
        return rows
    rows.extend(
        _row(box, " " * INDENT + line, content)
        for line in _wrap(text, content - INDENT)
    )
    if message.get("body_truncated"):
        rows.append(_row(box, " " * INDENT + ui.dim("[body truncated]"), content))
    return rows


def _mail_attachment(
    ui: object, box: dict[str, str], item: object, content: int
) -> list[str]:
    if isinstance(item, dict):
        name = _clean(str(item.get("filename") or item.get("name") or "attachment"))
        size = item.get("size")
        ident = item.get("id")
        detail = name
        if size is not None:
            detail += f"  ({size} bytes)"
        if ident:
            detail += f"  {_clean(str(ident))}"
    else:
        detail = _clean(str(item))
    tag = "[attachment]"
    room = content - INDENT - len(tag) - 1
    if room >= 8:
        parts = _wrap(detail, room)
        rows = [_row(box, " " * INDENT + ui.dim(tag) + " " + parts[0], content)]
        rows.extend(
            _row(box, " " * (INDENT + len(tag) + 1) + part, content)
            for part in parts[1:]
        )
        return rows
    rows = [_row(box, ui.dim(tag), content)]
    pad = " " * INDENT if content >= len(tag) + INDENT else ""
    rows.extend(
        _row(box, pad + part, content) for part in _wrap(detail, content - len(pad))
    )
    return rows


def _attachment(ui: object, box: dict[str, str], name: str, content: int) -> list[str]:
    tag = "[attachment]"
    room = content - INDENT - len(tag) - 1
    if room >= 8:
        parts = _wrap(name, room)
        rows = [_row(box, " " * INDENT + ui.dim(tag) + " " + parts[0], content)]
        rows.extend(
            _row(box, " " * (INDENT + len(tag) + 1) + part, content)
            for part in parts[1:]
        )
        return rows
    rows = [_row(box, ui.dim(tag), content)]
    pad = " " * INDENT if content >= len(tag) + INDENT else ""
    rows.extend(
        _row(box, pad + part, content) for part in _wrap(name, content - len(pad))
    )
    return rows


def _wrap(text: str, width: int) -> list[str]:
    width = max(1, width)
    lines: list[str] = []
    for raw in text.split("\n"):
        raw = raw.expandtabs(4).strip()
        if not raw:
            lines.append("")
            continue
        wrapped = textwrap.wrap(
            raw,
            width=width,
            break_long_words=True,
            break_on_hyphens=False,
        )
        lines.extend(wrapped or [""])
    return lines


def _clean(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return "".join(char for char in text if char in "\n\t" or char.isprintable())
