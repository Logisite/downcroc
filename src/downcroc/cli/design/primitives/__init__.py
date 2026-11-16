"""Primitive bricks: atoms with zero app knowledge."""

from downcroc.cli.design.primitives.callout import Callout
from downcroc.cli.design.primitives.card import Card
from downcroc.cli.design.primitives.code_panel import (
    CodePanel,
    sample_panel,
    sample_shell,
)
from downcroc.cli.design.primitives.keybar import keybar, keycap
from downcroc.cli.design.primitives.rule import divider, hairline
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
    "Callout",
    "Card",
    "CodePanel",
    "Prose",
    "TableView",
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
    "strong",
    "truncate",
]
