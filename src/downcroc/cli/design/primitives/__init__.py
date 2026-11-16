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
from downcroc.cli.design.primitives.icon import icon, status_dot
from downcroc.cli.design.primitives.key_value import KeyValue
from downcroc.cli.design.primitives.keybar import keybar, keycap
from downcroc.cli.design.primitives.list_block import ListBlock, ListItem
from downcroc.cli.design.primitives.nav import NavItem, TocItem
from downcroc.cli.design.primitives.panel import Panel
from downcroc.cli.design.primitives.rule import divider, hairline
from downcroc.cli.design.primitives.section_header import SectionHeader
from downcroc.cli.design.primitives.spacer import spacer
from downcroc.cli.design.primitives.table_view import TableView
from downcroc.cli.design.primitives.tag_list import TagList
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
from downcroc.cli.design.primitives.toast import Toast

__all__ = [
    "Blockquote",
    "Callout",
    "Card",
    "CodePanel",
    "EmptyState",
    "KeyValue",
    "ListBlock",
    "ListItem",
    "NavItem",
    "Panel",
    "Prose",
    "SectionHeader",
    "TableView",
    "TagList",
    "Toast",
    "TocItem",
    "badge",
    "breadcrumb",
    "chip",
    "divider",
    "hairline",
    "heading",
    "icon",
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
    "status_dot",
    "strong",
    "truncate",
]
