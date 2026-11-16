"""Directive preprocessing and fenced/inline directive resolution."""

from __future__ import annotations

import re

from markdown_it import MarkdownIt

from downcroc.cli.docs.content.inlines import inline_text, inlines_from_text
from downcroc.cli.docs.content.nodes import (
    Block,
    Callout,
    CollapsibleBlock,
    HtmlBlock,
    Paragraph,
    TabItem,
    TabsBlock,
)

_ADMONITION = re.compile(r'^!!!\s+([a-zA-Z]+)(?:\s+"([^"]*)")?\s*$')


def md() -> MarkdownIt:
    return (
        MarkdownIt("commonmark", {"html": False, "linkify": True})
        .enable("table")
        .enable("strikethrough")
    )


def preprocess_admonitions(source: str) -> str:
    lines = source.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        m = _ADMONITION.match(lines[i])
        if not m:
            out.append(lines[i])
            i += 1
            continue
        tone = (m.group(1) or "note").lower()
        title = m.group(2) or tone.title()
        body: list[str] = []
        i += 1
        while i < len(lines) and (lines[i] == "" or lines[i].startswith("    ")):
            body.append(lines[i][4:] if lines[i].startswith("    ") else "")
            i += 1
        out.append(f':::callout{{tone={tone} title="{title}"}}')
        out.extend(body)
        out.append(":::")
    return "\n".join(out)


def preprocess_directives(source: str) -> str:
    lines = source.splitlines()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(":::details"):
            title, open_flag = _directive_title_open(stripped, "details")
            out.append(f':::details{{title="{title}" open={str(open_flag).lower()}}}')
            continue
        if stripped.startswith(":::collapsible"):
            title, open_flag = _directive_title_open(stripped, "collapsible")
            out.append(f':::details{{title="{title}" open={str(open_flag).lower()}}}')
            continue
        if stripped == ":::tabs" or stripped.startswith(":::tabs{"):
            out.append(":::tabs")
            continue
        if stripped.startswith(":::tab"):
            title, _ = _directive_title_open(stripped, "tab")
            out.append(f':::tab{{title="{title}"}}')
            continue
        out.append(line)
    return "\n".join(out)


def _directive_title_open(line: str, name: str) -> tuple[str, bool]:
    title = name.title()
    open_flag = False
    m = re.search(r"\[([^\]]+)\]", line)
    if m:
        title = m.group(1).strip() or title
    if "{open}" in line or " open" in line or "open=true" in line.lower():
        open_flag = True
    m2 = re.search(r'title="([^"]*)"', line)
    if m2:
        title = m2.group(1)
    return title, open_flag


def resolve_directive_blocks(blocks: list[Block], parse_text_blocks) -> list[Block]:
    out: list[Block] = []
    i = 0
    while i < len(blocks):
        b = blocks[i]
        if isinstance(b, Paragraph):
            text = b.text.strip()
            bundled = blocks_from_directive_text(text, parse_text_blocks)
            if bundled is not None:
                out.extend(bundled)
                i += 1
                continue
            html_special = special_from_html_or_directive(text, parse_text_blocks)
            if html_special is not None and "<details" in text.lower():
                out.append(html_special)
                i += 1
                continue
            if text.startswith(":::callout{"):
                block, i = consume_callout_directive(blocks, i)
                out.append(block)
                continue
            if text.startswith(":::details{"):
                block, i = consume_details_directive(blocks, i, parse_text_blocks)
                if block is not None:
                    out.append(block)
                    continue
            if text == ":::tabs" or text.startswith(":::tabs{"):
                block, i = consume_tabs_directive(blocks, i)
                if block is not None:
                    out.append(block)
                    continue
        if isinstance(b, HtmlBlock):
            special = special_from_html_or_directive(b.html, parse_text_blocks)
            if special is not None:
                out.append(special)
                i += 1
                continue
        out.append(b)
        i += 1
    return out


def blocks_from_directive_text(text: str, parse_text_blocks) -> list[Block] | None:
    stripped = text.strip()
    if stripped.lower().startswith("<details") and stripped.lower().endswith(
        "</details>"
    ):
        special = special_from_html_or_directive(stripped, parse_text_blocks)
        return [special] if special else None
    if not stripped.startswith(":::") or "\n" not in stripped:
        return None
    if not stripped.startswith(
        (":::tabs", ":::details", ":::callout", ":::collapsible")
    ):
        return None
    lines = [line for line in stripped.splitlines()]
    paras: list[Block] = []
    for line in lines:
        if line.strip() == "":
            continue
        paras.append(
            Paragraph(text=line.strip(), inlines=tuple(inlines_from_text(line.strip())))
        )
    resolved = resolve_directive_blocks_no_bundle(paras, parse_text_blocks)
    kinds = {getattr(b, "kind", "") for b in resolved}
    if kinds & {"callout", "collapsible", "tabs"}:
        return resolved
    return None


def resolve_directive_blocks_no_bundle(
    blocks: list[Block], parse_text_blocks
) -> list[Block]:
    out: list[Block] = []
    i = 0
    while i < len(blocks):
        b = blocks[i]
        if isinstance(b, Paragraph):
            text = b.text.strip()
            if text.startswith(":::callout{"):
                block, i = consume_callout_directive(blocks, i)
                out.append(block)
                continue
            if text.startswith(":::details{"):
                block, i = consume_details_directive(blocks, i, parse_text_blocks)
                if block is not None:
                    out.append(block)
                    continue
            if text == ":::tabs" or text.startswith(":::tabs{"):
                block, i = consume_tabs_directive(blocks, i)
                if block is not None:
                    out.append(block)
                    continue
        out.append(b)
        i += 1
    return out


def consume_callout_directive(blocks: list[Block], i: int) -> tuple[Callout, int]:
    b = blocks[i]
    assert isinstance(b, Paragraph)
    m = re.search(r"tone=([^\s}]+)", b.text)
    t = re.search(r'title="([^"]*)"', b.text)
    tone = m.group(1) if m else "note"
    title = t.group(1) if t else tone.title()
    lines = b.text.splitlines()
    body_seed: list[str] = []
    if lines and lines[0].startswith(":::callout{"):
        rest = lines[1:]
        if rest and rest[-1].strip() == ":::":
            rest = rest[:-1]
            for line in rest:
                if line.strip():
                    body_seed.append(line)
            inner_seed: list[Block] = []
            if body_seed:
                txt = "\n".join(body_seed).strip()
                inner_seed.append(
                    Paragraph(
                        text=inline_text(txt), inlines=tuple(inlines_from_text(txt))
                    )
                )
            return Callout(tone=tone, title=title, blocks=tuple(inner_seed)), i + 1
        for line in rest:
            if line.strip():
                body_seed.append(line)
    inner: list[Block] = []
    if body_seed:
        txt = "\n".join(body_seed).strip()
        inner.append(
            Paragraph(text=inline_text(txt), inlines=tuple(inlines_from_text(txt)))
        )
    j = i + 1
    while j < len(blocks):
        cur = blocks[j]
        if isinstance(cur, Paragraph) and cur.text.strip() == ":::":
            j += 1
            break
        if isinstance(cur, Paragraph) and cur.text.strip().endswith("\n:::"):
            txt = cur.text[: cur.text.rfind("\n:::")].rstrip()
            if txt:
                inner.append(
                    Paragraph(
                        text=inline_text(txt), inlines=tuple(inlines_from_text(txt))
                    )
                )
            j += 1
            break
        inner.append(cur)
        j += 1
    return Callout(tone=tone, title=title, blocks=tuple(inner)), j


def consume_details_directive(
    blocks: list[Block], i: int, parse_text_blocks
) -> tuple[CollapsibleBlock | None, int]:
    b = blocks[i]
    assert isinstance(b, Paragraph)
    title_m = re.search(r'title="([^"]*)"', b.text)
    open_m = re.search(r"open=(true|false)", b.text)
    title = title_m.group(1) if title_m else "Details"
    open_flag = bool(open_m and open_m.group(1) == "true")
    lines = b.text.splitlines()
    body_seed: list[str] = []
    if lines and lines[0].startswith(":::details{"):
        rest = lines[1:]
        if rest and rest[-1].strip() == ":::":
            rest = rest[:-1]
            for line in rest:
                if line.strip():
                    body_seed.append(line)
            inner_seed: list[Block] = []
            if body_seed:
                inner_seed = parse_text_blocks("\n".join(body_seed))
            return (
                CollapsibleBlock(title=title, open=open_flag, blocks=tuple(inner_seed)),
                i + 1,
            )
        for line in rest:
            if line.strip():
                body_seed.append(line)
    inner: list[Block] = []
    if body_seed:
        inner.extend(parse_text_blocks("\n".join(body_seed)))
    j = i + 1
    while j < len(blocks):
        cur = blocks[j]
        if isinstance(cur, Paragraph) and cur.text.strip() == ":::":
            j += 1
            break
        if isinstance(cur, Paragraph) and cur.text.strip().endswith("\n:::"):
            txt = cur.text[: cur.text.rfind("\n:::")].rstrip()
            if txt:
                inner.extend(parse_text_blocks(txt))
            j += 1
            break
        inner.append(cur)
        j += 1
    return CollapsibleBlock(title=title, open=open_flag, blocks=tuple(inner)), j


def consume_tabs_directive(blocks: list[Block], i: int) -> tuple[TabsBlock | None, int]:
    items: list[TabItem] = []
    current_title = "Tab"
    current_inner: list[Block] = []
    in_tab = False
    j = i + 1
    while j < len(blocks):
        cur = blocks[j]
        if isinstance(cur, Paragraph):
            text = cur.text.strip()
            if text.startswith(":::tab{"):
                if in_tab:
                    items.append(
                        TabItem(title=current_title, blocks=tuple(current_inner))
                    )
                m = re.search(r'title="([^"]*)"', text)
                current_title = m.group(1) if m else "Tab"
                current_inner = []
                in_tab = True
                j += 1
                continue
            if text == ":::":
                if in_tab:
                    items.append(
                        TabItem(title=current_title, blocks=tuple(current_inner))
                    )
                    current_inner = []
                    in_tab = False
                    j += 1
                    if j < len(blocks) and isinstance(blocks[j], Paragraph):
                        nxt = blocks[j].text.strip()
                        if nxt.startswith(":::tab{"):
                            continue
                        if nxt == ":::":
                            j += 1
                    break
                j += 1
                break
        if in_tab:
            current_inner.append(cur)
        j += 1
    if in_tab:
        items.append(TabItem(title=current_title, blocks=tuple(current_inner)))
    if not items:
        return None, j
    return TabsBlock(items=tuple(items), active=0), j


def special_from_html_or_directive(content: str, parse_text_blocks) -> Block | None:
    stripped = content.strip()
    if stripped.startswith((":::details{", ":::tabs")):
        inner = parse_text_blocks(stripped)
        if inner:
            return inner[0]
    m = re.search(
        r"<details(?P<attrs>[^>]*)>\s*<summary>(?P<title>.*?)</summary>(?P<body>.*)</details>",
        stripped,
        re.IGNORECASE | re.DOTALL,
    )
    if m:
        attrs = m.group("attrs") or ""
        title = re.sub(r"<[^>]+>", "", m.group("title")).strip() or "Details"
        open_flag = "open" in attrs.lower()
        body = m.group("body").strip()
        inner = parse_text_blocks(body) if body else []
        return CollapsibleBlock(title=title, open=open_flag, blocks=tuple(inner))
    return None


def extract_callout(blocks: list[Block]) -> Callout | None:
    if not blocks:
        return None
    first = blocks[0]
    if isinstance(first, Paragraph) and first.text.startswith(":::callout{"):
        m = re.search(r"tone=([^\s}]+)", first.text)
        t = re.search(r'title="([^"]*)"', first.text)
        tone = m.group(1) if m else "note"
        title = t.group(1) if t else tone.title()
        inner = [
            b
            for b in blocks[1:]
            if not (isinstance(b, Paragraph) and b.text.strip() == ":::")
        ]
        return Callout(tone=tone, title=title, blocks=tuple(inner))
    return None


def callout_from_directive(content: str, parse_text_blocks) -> Callout | None:
    if not content.startswith(":::callout"):
        return None
    lines = content.splitlines()
    if not lines:
        return None
    head = lines[0]
    m = re.search(r"tone=([^\s}]+)", head)
    t = re.search(r'title="([^"]*)"', head)
    tone = m.group(1) if m else "note"
    title = t.group(1) if t else tone.title()
    body_lines = lines[1:]
    if body_lines and body_lines[-1].strip() == ":::":
        body_lines = body_lines[:-1]
    body = "\n".join(body_lines).strip("\n")
    inner = parse_text_blocks(body) if body else []
    return Callout(tone=tone, title=title, blocks=tuple(inner))
