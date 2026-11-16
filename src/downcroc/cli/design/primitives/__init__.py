"""Primitive bricks: atoms with zero app knowledge."""

from downcroc.cli.design.primitives.badge import badge
from downcroc.cli.design.primitives.blockquote import Blockquote
from downcroc.cli.design.primitives.callout import Callout
from downcroc.cli.design.primitives.card import Card
from downcroc.cli.design.primitives.code_panel import (
    CodePanel,
    sample_panel,
    sample_shell,
)
from downcroc.cli.design.primitives.empty_state import EmptyState
from downcroc.cli.design.primitives.key_value import KeyValue
from downcroc.cli.design.primitives.keybar import keybar, keycap
from downcroc.cli.design.primitives.list_block import ListBlock, ListItem
from downcroc.cli.design.primitives.panel import Panel
from downcroc.cli.design.primitives.rule import divider, hairline
from downcroc.cli.design.primitives.spacer import spacer
from downcroc.cli.design.primitives.table_view import TableView
from downcroc.cli.design.primitives.text import (
    Prose,
    breadcrumb,
    chip,
    heading,
    inline_code,
    label,
    link_text,
    muted,
    prose,
    strong,
    truncate,
)

__all__ = [
    "Blockquote",
    "Callout",
    "Card",
    "CodePanel",
    "EmptyState",
    "KeyValue",
    "ListBlock",
    "ListItem",
    "Panel",
    "Prose",
    "TableView",
    "badge",
    "breadcrumb",
    "chip",
    "divider",
    "hairline",
    "heading",
    "inline_code",
    "keybar",
    "keycap",
    "label",
    "link_text",
    "muted",
    "prose",
    "sample_panel",
    "sample_shell",
    "spacer",
    "strong",
    "truncate",
]
