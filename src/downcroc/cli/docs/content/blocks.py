"""Block-level markdown parsing."""

from __future__ import annotations

import re

from markdown_it.token import Token

from downcroc.cli.docs.content.directives import (
    callout_from_directive,
    extract_callout,
    md,
    preprocess_admonitions,
    preprocess_directives,
    resolve_directive_blocks,
    special_from_html_or_directive,
)
from downcroc.cli.docs.content.inlines import (
    attr,
    inline_text,
    inlines_from_text,
    parse_inlines,
)
from downcroc.cli.docs.content.nodes import (
    Block,
    BlockQuote,
    CodeBlock,
    Document,
    Heading,
    HorizontalRule,
    HtmlBlock,
    ImageBlock,
    ListBlock,
    ListItem,
    Paragraph,
    TableBlock,
)
from downcroc.cli.docs.content.slugify import unique_slug

_TASK_RE = re.compile(r"^\s*\[( |x|X)\]\s+")


def parse_document(source: str) -> Document:
    meta, body = _frontmatter(source)
    processed = preprocess_directives(preprocess_admonitions(body))
    tokens = md().parse(processed)
    slug_seen: dict[str, int] = {}
    blocks, headings = _parse_blocks(tokens, slug_seen)
    blocks = resolve_directive_blocks(
        blocks, lambda text: _blocks_from_text(text, slug_seen)
    )
    title = str(meta.get("title") or "")
    if not title and headings:
        title = headings[0].text
    description = str(meta.get("description") or "")
    return Document(
        source=source,
        meta=meta,
        blocks=tuple(blocks),
        title=title,
        description=description,
        headings=tuple(headings),
    )


def _frontmatter(source: str) -> tuple[dict[str, object], str]:
    # local import-free behavior kept in sync with frontmatter module by parser facade
    from downcroc.cli.docs.content.frontmatter import frontmatter

    return frontmatter(source)


def _blocks_from_text(text: str, slug_seen: dict[str, int]) -> list[Block]:
    text = text.strip("\n")
    if not text:
        return []
    tokens = md().parse(preprocess_directives(preprocess_admonitions(text)))
    inner, _ = _parse_blocks(tokens, slug_seen)
    return inner


def _parse_blocks(
    tokens: list[Token], slug_seen: dict[str, int]
) -> tuple[list[Block], list[Heading]]:
    blocks: list[Block] = []
    headings: list[Heading] = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t.type == "heading_open":
            level = int(t.tag[1]) if t.tag and t.tag.startswith("h") else 1
            inline = tokens[i + 1] if i + 1 < len(tokens) else None
            text = inline_text(inline.content) if inline else ""
            inlines = parse_inlines(inline)
            slug = unique_slug(text or "section", slug_seen)
            h = Heading(level=level, text=text, slug=slug, inlines=inlines)
            blocks.append(h)
            headings.append(h)
            i += 3
            continue
        if t.type == "paragraph_open":
            inline = tokens[i + 1] if i + 1 < len(tokens) else None
            content = inline.content if inline else ""
            img = _standalone_image(inline)
            if img is not None:
                blocks.append(img)
            elif content.startswith(":::callout{") and content.endswith("}"):
                blocks.append(Paragraph(text=content, inlines=parse_inlines(inline)))
            else:
                stripped, checked = _strip_task_prefix(content)
                if checked is not None and inline is not None:
                    inline = Token("inline", "", 0)
                    inline.content = stripped
                    inline.children = None
                blocks.append(
                    Paragraph(
                        text=inline_text(stripped),
                        inlines=parse_inlines(inline),
                    )
                )
            i += 3
            continue
        if t.type == "fence" or t.type == "code_block":
            info = (t.info or "").strip()
            lang = info.split()[0] if info else ""
            blocks.append(
                CodeBlock(code=t.content.rstrip("\n"), language=lang, info=info)
            )
            i += 1
            continue
        if t.type == "blockquote_open":
            inner, i = _parse_container(tokens, i + 1, "blockquote_close", slug_seen)
            callout = extract_callout(inner)
            blocks.append(callout if callout else BlockQuote(blocks=tuple(inner)))
            i += 1
            continue
        if t.type == "bullet_list_open" or t.type == "ordered_list_open":
            ordered = t.type == "ordered_list_open"
            start = int(attr(t, "start") or "1")
            items, i = _parse_list_items(
                tokens, i + 1, t.type.replace("_open", "_close"), slug_seen
            )
            blocks.append(ListBlock(ordered=ordered, start=start, items=tuple(items)))
            i += 1
            continue
        if t.type == "table_open":
            table, i = _parse_table(tokens, i + 1)
            blocks.append(table)
            i += 1
            continue
        if t.type == "hr":
            blocks.append(HorizontalRule())
            i += 1
            continue
        if t.type == "html_block":
            content = t.content.strip()
            callout = callout_from_directive(
                content, lambda text: _blocks_from_text(text, slug_seen)
            )
            if callout is not None:
                blocks.append(callout)
            else:
                special = special_from_html_or_directive(
                    content, lambda text: _blocks_from_text(text, slug_seen)
                )
                if special is not None:
                    blocks.append(special)
                else:
                    blocks.append(HtmlBlock(html=content))
            i += 1
            continue
        i += 1
    blocks = resolve_directive_blocks(
        blocks, lambda text: _blocks_from_text(text, slug_seen)
    )
    return blocks, headings


def _standalone_image(inline: Token | None) -> ImageBlock | None:
    if inline is None or not inline.children:
        return None
    ch = [c for c in inline.children if c.type not in {"softbreak", "hardbreak"}]
    if len(ch) == 1 and ch[0].type == "image":
        t = ch[0]
        return ImageBlock(
            alt=t.content or attr(t, "alt"), src=attr(t, "src"), title=attr(t, "title")
        )
    return None


def _parse_container(
    tokens: list[Token], i: int, close: str, slug_seen: dict[str, int]
) -> tuple[list[Block], int]:
    inner_tokens: list[Token] = []
    depth = 1
    open_type = close.replace("_close", "_open")
    while i < len(tokens):
        t = tokens[i]
        if t.type == open_type:
            depth += 1
        if t.type == close:
            depth -= 1
            if depth == 0:
                break
        inner_tokens.append(t)
        i += 1
    blocks, _ = _parse_blocks(inner_tokens, slug_seen)
    return blocks, i


def _parse_list_items(
    tokens: list[Token], i: int, close: str, slug_seen: dict[str, int]
) -> tuple[list[ListItem], int]:
    items: list[ListItem] = []
    while i < len(tokens) and tokens[i].type != close:
        t = tokens[i]
        if t.type == "list_item_open":
            checked = _task_checked(t)
            inner, i = _parse_container(tokens, i + 1, "list_item_close", slug_seen)
            if checked is None and inner:
                first = inner[0]
                if isinstance(first, Paragraph):
                    stripped, task_checked = _strip_task_prefix(first.text)
                    if task_checked is not None:
                        checked = task_checked
                        inner = [
                            Paragraph(
                                text=stripped,
                                inlines=tuple(inlines_from_text(stripped)),
                            ),
                            *inner[1:],
                        ]
            items.append(ListItem(blocks=tuple(inner), checked=checked))
            i += 1
            continue
        i += 1
    return items, i


def _task_checked(token: Token) -> bool | None:
    cls = attr(token, "class")
    if "task-list-item" in cls:
        return "checked" in cls or "is-checked" in cls
    markup = getattr(token, "markup", "") or ""
    if markup in {"-", "*", "+"} and "task" in (attr(token, "data-type") or ""):
        return False
    return None


def _strip_task_prefix(text: str) -> tuple[str, bool | None]:
    m = _TASK_RE.match(text)
    if not m:
        return text, None
    checked = m.group(1).lower() == "x"
    return text[m.end() :], checked


def _parse_table(tokens: list[Token], i: int) -> tuple[TableBlock, int]:
    headers: list[tuple[object, ...]] = []
    aligns: list[str] = []
    rows: list[tuple[tuple[object, ...], ...]] = []
    in_thead = in_tbody = False
    current_row: list[tuple[object, ...]] = []
    while i < len(tokens) and tokens[i].type != "table_close":
        t = tokens[i]
        if t.type == "thead_open":
            in_thead = True
        elif t.type == "thead_close":
            in_thead = False
        elif t.type == "tbody_open":
            in_tbody = True
        elif t.type == "tbody_close":
            in_tbody = False
        elif t.type == "tr_open":
            current_row = []
        elif t.type == "tr_close":
            if in_thead and not headers:
                headers = current_row
            elif in_tbody or headers:
                rows.append(tuple(current_row))
            current_row = []
        elif t.type in {"th_open", "td_open"}:
            style = attr(t, "style")
            align = "left"
            if "center" in style:
                align = "center"
            elif "right" in style:
                align = "right"
            if in_thead:
                aligns.append(align)
            inline = tokens[i + 1] if i + 1 < len(tokens) else None
            current_row.append(parse_inlines(inline))
            i += 2
            continue
        i += 1
    if aligns and len(aligns) != len(headers):
        aligns = (aligns + ["left"] * len(headers))[: len(headers)]
    return TableBlock(headers=tuple(headers), aligns=tuple(aligns), rows=tuple(rows)), i
