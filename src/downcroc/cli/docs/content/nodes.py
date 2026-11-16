"""Typed nodes for parsed markdown documents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class Inline:
    """Inline content node."""

    kind: Literal[
        "text",
        "strong",
        "em",
        "code",
        "link",
        "image",
        "softbreak",
        "hardbreak",
        "wikilink",
        "strike",
    ]
    text: str = ""
    href: str = ""
    title: str = ""
    children: tuple[Inline, ...] = ()


@dataclass(frozen=True)
class Block:
    """Base marker for block nodes."""

    kind: str


@dataclass(frozen=True)
class Heading(Block):
    kind: Literal["heading"] = "heading"
    level: int = 1
    text: str = ""
    slug: str = ""
    inlines: tuple[Inline, ...] = ()


@dataclass(frozen=True)
class Paragraph(Block):
    kind: Literal["paragraph"] = "paragraph"
    text: str = ""
    inlines: tuple[Inline, ...] = ()


@dataclass(frozen=True)
class CodeBlock(Block):
    kind: Literal["code"] = "code"
    code: str = ""
    language: str = ""
    info: str = ""


@dataclass(frozen=True)
class BlockQuote(Block):
    kind: Literal["blockquote"] = "blockquote"
    blocks: tuple[Block, ...] = ()


@dataclass(frozen=True)
class Callout(Block):
    kind: Literal["callout"] = "callout"
    tone: str = "note"
    title: str = ""
    blocks: tuple[Block, ...] = ()


@dataclass(frozen=True)
class ListItem(Block):
    kind: Literal["list_item"] = "list_item"
    blocks: tuple[Block, ...] = ()
    checked: bool | None = None


@dataclass(frozen=True)
class ListBlock(Block):
    kind: Literal["list"] = "list"
    ordered: bool = False
    start: int = 1
    tight: bool = True
    items: tuple[ListItem, ...] = ()


@dataclass(frozen=True)
class TableBlock(Block):
    kind: Literal["table"] = "table"
    headers: tuple[tuple[Inline, ...], ...] = ()
    aligns: tuple[str, ...] = ()
    rows: tuple[tuple[tuple[Inline, ...], ...], ...] = ()


@dataclass(frozen=True)
class HorizontalRule(Block):
    kind: Literal["hr"] = "hr"


@dataclass(frozen=True)
class ImageBlock(Block):
    kind: Literal["image"] = "image"
    alt: str = ""
    src: str = ""
    title: str = ""


@dataclass(frozen=True)
class HtmlBlock(Block):
    kind: Literal["html"] = "html"
    html: str = ""


@dataclass(frozen=True)
class CollapsibleBlock(Block):
    kind: Literal["collapsible"] = "collapsible"
    title: str = ""
    open: bool = False
    blocks: tuple[Block, ...] = ()


@dataclass(frozen=True)
class TabItem:
    title: str
    blocks: tuple[Block, ...] = ()


@dataclass(frozen=True)
class TabsBlock(Block):
    kind: Literal["tabs"] = "tabs"
    items: tuple[TabItem, ...] = ()
    active: int = 0


@dataclass(frozen=True)
class Document:
    """Parsed document with frontmatter metadata and typed blocks."""

    source: str
    meta: dict[str, object] = field(default_factory=dict)
    blocks: tuple[Block, ...] = ()
    title: str = ""
    description: str = ""
    headings: tuple[Heading, ...] = ()
