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
from downcroc.cli.design.primitives.text import chip, heading, label, prose

__all__ = [
    "Callout",
    "Card",
    "CodePanel",
    "TableView",
    "chip",
    "divider",
    "hairline",
    "heading",
    "keybar",
    "keycap",
    "label",
    "prose",
    "sample_panel",
    "sample_shell",
]
