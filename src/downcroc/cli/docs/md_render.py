"""Render typed markdown content using the downcroc design system."""

from __future__ import annotations

import re

from rich.console import Group, RenderableType
from rich.padding import Padding
from rich.text import Text

from downcroc.cli.design.components.doc_header import DocHeader
from downcroc.cli.design.components.figure_block import FigureBlock
from downcroc.cli.design.components.pager import Pager
from downcroc.cli.design.primitives.alert import Alert
from downcroc.cli.design.primitives.blockquote import Blockquote
from downcroc.cli.design.primitives.code_panel import CodePanel
from downcroc.cli.design.primitives.collapsible import Collapsible
from downcroc.cli.design.primitives.rule import divider
from downcroc.cli.design.primitives.separator import separator
from downcroc.cli.design.primitives.spacer import spacer
from downcroc.cli.design.primitives.table_view import TableView
from downcroc.cli.design.primitives.tabs import Tabs
from downcroc.cli.design.primitives.text import heading
from downcroc.cli.design.theme import DEFAULT, Theme
from downcroc.cli.docs.content.nodes import (
    Block,
    BlockQuote,
    CodeBlock,
    CollapsibleBlock,
    Document,
    Heading,
    HorizontalRule,
    HtmlBlock,
    ImageBlock,
    Inline,
    ListBlock,
    Paragraph,
    TableBlock,
    TabsBlock,
)
from downcroc.cli.docs.content.nodes import (
    Callout as CalloutNode,
)


def _inline_text(inlines: tuple[Inline, ...]) -> str:
    parts: list[str] = []
    for node in inlines:
        if node.kind in {"text", "code", "wikilink"}:
            parts.append(node.text)
        elif node.kind == "link":
            parts.append(_inline_text(node.children) or node.text or node.href)
        elif node.kind in {"strong", "em", "strike"}:
            parts.append(_inline_text(node.children))
        elif node.kind == "image":
            parts.append(node.text or node.href)
        elif node.kind == "softbreak":
            parts.append(" ")
        elif node.kind == "hardbreak":
            parts.append("\n")
    return "".join(parts)


def render_inlines(inlines: tuple[Inline, ...], theme: Theme = DEFAULT) -> Text:
    out = Text()
    for node in inlines:
        if node.kind == "text":
            out.append(node.text, style=theme.style("fg_secondary"))
        elif node.kind == "softbreak":
            out.append(" ")
        elif node.kind == "hardbreak":
            out.append("\n")
        elif node.kind == "code":
            out.append(node.text, style=theme.style("accent_strong", on="bg_raised"))
            out.append(" ")
            # trim accidental trailing space effect by rebuilding is complex; simple padding look
        elif node.kind == "strong":
            child = render_inlines(node.children, theme)
            child.stylize(theme.style("fg_primary", bold=True))
            out.append_text(child)
        elif node.kind == "em":
            child = render_inlines(node.children, theme)
            child.stylize(theme.style("fg_secondary", italic=True))
            out.append_text(child)
        elif node.kind == "strike":
            child = render_inlines(node.children, theme)
            child.stylize(theme.style("fg_faint", strike=True))
            out.append_text(child)
        elif node.kind == "link":
            label_text = _inline_text(node.children) or node.text or node.href
            link = Text(label_text, style=theme.style("fg_link", underline=True))
            if node.href:
                link.stylize(f"link {node.href}")
            out.append_text(link)
        elif node.kind == "wikilink":
            target = node.href or node.text
            label_text = node.text or target
            out.append(label_text, style=theme.style("accent", underline=True))
        elif node.kind == "image":
            label_text = node.text or node.href or "image"
            out.append(f"[image: {label_text}]", style=theme.style("fg_muted"))
        else:
            if node.text:
                out.append(node.text, style=theme.style("fg_secondary"))
    # normalize inline-code spacing artifacts from simple append
    plain = out.plain
    if plain.endswith("  "):
        out = Text(plain.rstrip(), style=out.style)
    return out


class RichProse:
    """Prose block that wraps inline-styled Rich Text."""

    def __init__(self, text: Text, theme: Theme, *, width: int | None = None):
        self.text = text
        self.theme = theme
        self.width = width

    def __rich_console__(self, console, options):
        width = self.width or options.max_width
        t = self.text.copy()
        if not t.style:
            t.stylize(self.theme.style("fg_secondary"))
        try:
            lines = t.wrap(console, width, overflow="fold", no_wrap=False)
            yield from lines
            return
        except TypeError:
            pass
        lines = Text(t.plain, style=self.theme.style("fg_secondary")).wrap(
            console, width, overflow="fold", no_wrap=False
        )
        yield from lines

    def __rich_measure__(self, console, options):
        from rich.measure import Measurement

        width = self.width or options.max_width
        minimum = min(20, width) if width > 0 else 0
        return Measurement(minimum, max(width, minimum))


def _heading_block(block: Heading, theme: Theme) -> RenderableType:
    level = min(max(block.level, 1), 3)
    h = heading(block.text, theme, level=level)
    line = Text()
    line.append_text(h if isinstance(h, Text) else Text(str(h)))
    if block.slug:
        line.append(f"  #{block.slug}", style=theme.style("fg_faint"))
        line.append("  ⎘", style=theme.style("fg_faint"))
    parts: list[RenderableType] = [line]
    if level <= 2:
        parts.append(separator(theme, length=min(max(len(block.text) + 8, 24), 56)))
    parts.append(spacer(1, theme=theme))
    return Group(*parts)


def _blockquote_block(
    block: BlockQuote, theme: Theme, width: int | None
) -> RenderableType:
    body = [render_block(b, theme, width=width) for b in block.blocks]
    if len(block.blocks) == 1 and isinstance(block.blocks[0], Paragraph):
        text = _inline_text(block.blocks[0].inlines)
        return Group(Blockquote(text, "", theme), spacer(1, theme=theme))
    quote = Group(*body) if body else Text("", style=theme.style("fg_muted"))
    return Group(
        Padding(quote, (0, 0, 0, 2), style=theme.style("border_subtle")),
        spacer(1, theme=theme),
    )


def _callout_block(
    block: CalloutNode, theme: Theme, width: int | None
) -> RenderableType:
    if len(block.blocks) == 1 and isinstance(block.blocks[0], Paragraph):
        plain = _inline_text(block.blocks[0].inlines)
        return Group(
            Alert(block.title, plain, theme, tone=block.tone, width=width),
            spacer(1, theme=theme),
        )
    body = [render_block(b, theme, width=width) for b in block.blocks]
    return Group(
        Alert(block.title, Group(*body), theme, tone=block.tone, width=width),
        spacer(1, theme=theme),
    )


def _code_block(block: CodeBlock, theme: Theme, width: int | None) -> RenderableType:
    panel = CodePanel(
        block.code or "",
        theme,
        language=block.language or "text",
        filename=_filename_from_info(block.info),
        width=min(width or 80, 88),
    )
    return Group(panel, spacer(1, theme=theme))


def _filename_from_info(info: str) -> str:
    # support fenced info like: bash {title="install.sh"} or python filename.py (best effort)
    if not info:
        return ""
    m = re.search(r'(?:title|file|filename)=["\']([^"\']+)["\']', info)
    if m:
        return m.group(1)
    parts = info.split()
    if len(parts) >= 2 and "." in parts[1]:
        return parts[1]
    return ""


def render_block(
    block: Block, theme: Theme = DEFAULT, *, width: int | None = None
) -> RenderableType:
    if isinstance(block, Heading):
        return _heading_block(block, theme)
    if isinstance(block, Paragraph):
        text = render_inlines(block.inlines, theme)
        return Group(RichProse(text, theme, width=width), spacer(1, theme=theme))
    if isinstance(block, CodeBlock):
        return _code_block(block, theme, width)
    if isinstance(block, CalloutNode):
        return _callout_block(block, theme, width)
    if isinstance(block, BlockQuote):
        return _blockquote_block(block, theme, width)
    if isinstance(block, ListBlock):
        items = _render_list_items(block, theme, width=width)
        return Group(*items, spacer(1, theme=theme))
    if isinstance(block, CollapsibleBlock):
        inner = [render_block(b, theme, width=width) for b in block.blocks]
        body: RenderableType | None = Group(*inner) if inner else None
        return Group(
            Collapsible(
                block.title or "Details",
                body,
                open=block.open or bool(inner),
                theme=theme,
            ),
            spacer(1, theme=theme),
        )
    if isinstance(block, TabsBlock):
        tabs = []
        for idx, item in enumerate(block.items):
            inner = [render_block(b, theme, width=width) for b in item.blocks]
            body: RenderableType = Group(*inner) if inner else Text("")
            tabs.append((item.title or f"Tab {idx + 1}", body))
        if tabs:
            active = min(max(block.active, 0), len(tabs) - 1)
            return Group(Tabs(tabs, active=active, theme=theme), spacer(1, theme=theme))
        return spacer(1, theme=theme)
    if isinstance(block, HtmlBlock):
        html = block.html.strip()
        if not html:
            return spacer(1, theme=theme)
        preview = re.sub(r"<[^>]+>", "", html)
        preview = re.sub(r"\s+", " ", preview).strip()
        if preview:
            return Group(
                Padding(Text(preview, style=theme.style("fg_muted")), (0, 0, 1, 0))
            )
        return Group(
            Text("[html block]", style=theme.style("fg_faint")), spacer(1, theme=theme)
        )
    if isinstance(block, TableBlock):
        headers = [_inline_text(h) for h in block.headers]
        rows = [[_inline_text(cell) for cell in row] for row in block.rows]
        aligns = list(block.aligns) if block.aligns else None
        return Group(
            TableView(headers, rows, theme, align=aligns, zebra=True, compact=False),
            spacer(1, theme=theme),
        )
    if isinstance(block, HorizontalRule):
        return Group(divider(theme, width=min(width or 60, 72)), spacer(1, theme=theme))
    if isinstance(block, ImageBlock):
        label_text = block.alt or block.src or "image"
        caption = block.title or block.src
        fig = Text(f"[image] {label_text}", style=theme.style("fg_muted"))
        return FigureBlock(fig, caption, theme, width=width)
    return Group(
        Text(str(getattr(block, "kind", "block")), style=theme.style("fg_faint")),
        spacer(1, theme=theme),
    )


def _render_list_items(
    block: ListBlock, theme: Theme, *, width: int | None = None, level: int = 0
) -> list[RenderableType]:
    from downcroc.cli.design.primitives.list_block import ListItem as UIListItem

    out: list[RenderableType] = []
    num = block.start
    for item in block.items:
        marker = "•"
        if block.ordered:
            marker = f"{num}." if level == 0 else "◦"
            if level == 0:
                num += 1
        text = ""
        nested: list[RenderableType] = []
        for b in item.blocks:
            if isinstance(b, Paragraph) and not text:
                text = _inline_text(b.inlines)
            elif isinstance(b, ListBlock):
                nested.extend(
                    _render_list_items(b, theme, width=width, level=level + 1)
                )
            else:
                nested.append(render_block(b, theme, width=width))
        out.append(
            UIListItem(
                text or " ", theme, marker=marker, level=level, checked=item.checked
            )
        )
        out.extend(nested)
    return out


def render_document(
    doc: Document,
    theme: Theme = DEFAULT,
    *,
    width: int | None = None,
    skip_first_h1: str | None = None,
) -> Group:
    return Group(
        *[
            r
            for _anchor, r in render_document_sections(
                doc, theme, width=width, skip_first_h1=skip_first_h1
            )
        ]
    )


def render_document_sections(
    doc: Document,
    theme: Theme = DEFAULT,
    *,
    width: int | None = None,
    skip_first_h1: str | None = None,
) -> list[tuple[str | None, RenderableType]]:
    """Render document as ordered sections with optional heading anchors.

    This enables anchor-aware mounting/scroll strategies in interactive shells.
    """
    sections: list[tuple[str | None, RenderableType]] = []
    skipped = False
    current_anchor: str | None = None
    bucket: list[RenderableType] = []

    def flush() -> None:
        nonlocal bucket, current_anchor
        if bucket:
            sections.append((current_anchor, Group(*bucket)))
            bucket = []

    for block in doc.blocks:
        if (
            not skipped
            and skip_first_h1
            and isinstance(block, Heading)
            and block.level == 1
            and block.text.strip() == skip_first_h1.strip()
        ):
            skipped = True
            continue
        if isinstance(block, Heading):
            flush()
            current_anchor = block.slug or None
            bucket.append(render_block(block, theme, width=width))
            continue
        bucket.append(render_block(block, theme, width=width))
    flush()
    if not sections:
        return [(None, Group(*[]))]
    return sections


def render_page(
    doc: Document,
    *,
    title: str | None = None,
    description: str | None = None,
    breadcrumbs: list[str] | None = None,
    prev_next: tuple[tuple[str, str] | None, tuple[str, str] | None] | None = None,
    theme: Theme = DEFAULT,
    width: int | None = None,
) -> Group:
    return Group(
        *[
            r
            for _aid, r in render_page_sections(
                doc,
                title=title,
                description=description,
                breadcrumbs=breadcrumbs,
                prev_next=prev_next,
                theme=theme,
                width=width,
            )
        ]
    )


def render_page_sections(
    doc: Document,
    *,
    title: str | None = None,
    description: str | None = None,
    breadcrumbs: list[str] | None = None,
    prev_next: tuple[tuple[str, str] | None, tuple[str, str] | None] | None = None,
    theme: Theme = DEFAULT,
    width: int | None = None,
) -> list[tuple[str | None, RenderableType]]:
    """Render page as anchor-addressable sections (header, body sections, pager)."""
    sections: list[tuple[str | None, RenderableType]] = []
    page_title = title or doc.title or "Untitled"
    header = DocHeader(
        page_title,
        theme,
        breadcrumb_items=[(b, "default") for b in (breadcrumbs or [])] or None,
        lead=description if description is not None else doc.description,
        meta=[],
        width=width or 72,
    )
    sections.append(("__top__", header))
    sections.extend(
        render_document_sections(doc, theme, width=width, skip_first_h1=page_title)
    )
    if prev_next:
        prev, nxt = prev_next
        sections.append(
            (
                "__pager__",
                Pager(
                    theme,
                    prev_label=(prev[0] if prev else ""),
                    prev_target=(prev[1] if prev else ""),
                    next_label=(nxt[0] if nxt else ""),
                    next_target=(nxt[1] if nxt else ""),
                    width=width or 72,
                ),
            )
        )
    return sections


def slugify_heading(text: str) -> str:
    s = text.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "section"
