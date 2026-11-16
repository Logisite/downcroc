"""Typed markdown content model, parsing, and page indexing (Phase 4)."""

from downcroc.cli.docs.content.index import DocIndex, IndexedPage, build_index
from downcroc.cli.docs.content.nodes import (
    Block,
    BlockQuote,
    Callout,
    CodeBlock,
    CollapsibleBlock,
    Document,
    Heading,
    HorizontalRule,
    HtmlBlock,
    ImageBlock,
    Inline,
    ListBlock,
    ListItem,
    Paragraph,
    TabItem,
    TableBlock,
    TabsBlock,
)
from downcroc.cli.docs.content.parser import parse_document

__all__ = [
    "Block",
    "BlockQuote",
    "Callout",
    "CodeBlock",
    "CollapsibleBlock",
    "DocIndex",
    "Document",
    "Heading",
    "HorizontalRule",
    "HtmlBlock",
    "ImageBlock",
    "IndexedPage",
    "Inline",
    "ListBlock",
    "ListItem",
    "Paragraph",
    "TabItem",
    "TableBlock",
    "TabsBlock",
    "build_index",
    "parse_document",
]
