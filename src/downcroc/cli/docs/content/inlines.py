"""Inline markdown parsing helpers."""

from __future__ import annotations

import re

from markdown_it.token import Token

from downcroc.cli.docs.content.nodes import Inline

_WIKILINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")


def inline_text(content: str) -> str:
    # coarse plain text extraction for headings/search
    text = re.sub(r"`([^`]+)`", r"\1", content)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(
        r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", lambda m: m.group(2) or m.group(1), text
    )
    return text.strip()


def parse_inlines(token: Token | None) -> tuple[Inline, ...]:
    if token is None or not token.children:
        content = token.content if token else ""
        return inlines_from_text(content)
    result: list[Inline] = []
    i = 0
    children = token.children
    while i < len(children):
        t = children[i]
        if t.type == "text":
            result.extend(inlines_from_text(t.content))
        elif t.type == "code_inline":
            result.append(Inline(kind="code", text=t.content))
        elif t.type == "softbreak":
            result.append(Inline(kind="softbreak"))
        elif t.type == "hardbreak":
            result.append(Inline(kind="hardbreak"))
        elif t.type == "strong_open":
            inner, i = _collect_inline(children, i + 1, "strong_close")
            result.append(Inline(kind="strong", children=tuple(inner)))
        elif t.type == "em_open":
            inner, i = _collect_inline(children, i + 1, "em_close")
            result.append(Inline(kind="em", children=tuple(inner)))
        elif t.type == "s_open":
            inner, i = _collect_inline(children, i + 1, "s_close")
            result.append(Inline(kind="strike", children=tuple(inner)))
        elif t.type == "link_open":
            href = attr(t, "href")
            title = attr(t, "title")
            inner, i = _collect_inline(children, i + 1, "link_close")
            result.append(
                Inline(kind="link", href=href, title=title, children=tuple(inner))
            )
        elif t.type == "image":
            src = attr(t, "src")
            alt = t.content or attr(t, "alt")
            title = attr(t, "title")
            result.append(Inline(kind="image", text=alt, href=src, title=title))
        elif t.type == "html_inline":
            pass
        else:
            if t.content:
                result.extend(inlines_from_text(t.content))
        i += 1
    return tuple(result)


def inlines_from_text(text: str) -> list[Inline]:
    if not text:
        return []
    out: list[Inline] = []
    pos = 0
    for m in _WIKILINK.finditer(text):
        if m.start() > pos:
            out.append(Inline(kind="text", text=text[pos : m.start()]))
        target = m.group(1)
        label = m.group(2) or target
        out.append(Inline(kind="wikilink", text=label, href=target))
        pos = m.end()
    if pos < len(text):
        out.append(Inline(kind="text", text=text[pos:]))
    return out


def _collect_inline(
    children: list[Token], i: int, close: str
) -> tuple[list[Inline], int]:
    inner: list[Inline] = []
    while i < len(children) and children[i].type != close:
        t = children[i]
        if t.type == "text":
            inner.extend(inlines_from_text(t.content))
        elif t.type == "code_inline":
            inner.append(Inline(kind="code", text=t.content))
        elif t.type == "softbreak":
            inner.append(Inline(kind="softbreak"))
        elif t.type == "strong_open":
            nested, i = _collect_inline(children, i + 1, "strong_close")
            inner.append(Inline(kind="strong", children=tuple(nested)))
        elif t.type == "em_open":
            nested, i = _collect_inline(children, i + 1, "em_close")
            inner.append(Inline(kind="em", children=tuple(nested)))
        elif t.type == "s_open":
            nested, i = _collect_inline(children, i + 1, "s_close")
            inner.append(Inline(kind="strike", children=tuple(nested)))
        elif t.type == "link_open":
            href = attr(t, "href")
            title = attr(t, "title")
            nested, i = _collect_inline(children, i + 1, "link_close")
            inner.append(
                Inline(kind="link", href=href, title=title, children=tuple(nested))
            )
        i += 1
    return inner, i


def attr(token: Token, name: str) -> str:
    if token.attrs is None:
        return ""
    if isinstance(token.attrs, dict):
        return str(token.attrs.get(name, ""))
    for k, v in token.attrs:
        if k == name:
            return str(v)
    return ""
