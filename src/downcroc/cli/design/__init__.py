"""The downcroc design system.

Shared by all CLI apps: bricks render purely from props + theme, input is
normalized through the interaction layer, and the look is hand-painted Rich
segments over Textual's engine. See plan: downcroc-design-system.md.
"""

from downcroc.cli.design.primitives import (
    Callout,
    Card,
    CodePanel,
    TableView,
    chip,
    divider,
    hairline,
    heading,
    keybar,
    keycap,
    label,
    prose,
    sample_panel,
    sample_shell,
)
from downcroc.cli.design.theme import DEFAULT, Theme

__all__ = [
    "DEFAULT",
    "Callout",
    "Card",
    "CodePanel",
    "TableView",
    "Theme",
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
