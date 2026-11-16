"""Parse markdown source into typed content nodes (facade).

Implementation is split into focused modules:
- frontmatter.py: YAML-like frontmatter parsing
- inlines.py: inline token/text parsing
- directives.py: admonition/directive preprocessing and resolution
- blocks.py: block/token parsing and document assembly
"""

from __future__ import annotations

from downcroc.cli.docs.content.blocks import parse_document
from downcroc.cli.docs.content.directives import (
    callout_from_directive,
    extract_callout,
)
from downcroc.cli.docs.content.directives import (
    md as _md,
)
from downcroc.cli.docs.content.directives import (
    preprocess_admonitions as _preprocess_admonitions,
)
from downcroc.cli.docs.content.directives import (
    preprocess_directives as _preprocess_directives,
)
from downcroc.cli.docs.content.frontmatter import frontmatter
from downcroc.cli.docs.content.inlines import (
    attr as _attr,
)
from downcroc.cli.docs.content.inlines import (
    inline_text as _inline_text,
)
from downcroc.cli.docs.content.inlines import (
    inlines_from_text as _inlines_from_text,
)
from downcroc.cli.docs.content.inlines import (
    parse_inlines as _parse_inlines,
)

__all__ = [
    "_attr",
    "_callout_from_directive",
    "_extract_callout",
    "_inline_text",
    "_inlines_from_text",
    "_md",
    "_parse_inlines",
    "_preprocess_admonitions",
    "_preprocess_directives",
    "callout_from_directive",
    "extract_callout",
    "frontmatter",
    "parse_document",
]


def _extract_callout(blocks):
    return extract_callout(blocks)


def _callout_from_directive(content, slug_seen):
    # compatibility shim: old signature accepted slug_seen; new path resolves via blocks parser
    from downcroc.cli.docs.content.blocks import _blocks_from_text

    return callout_from_directive(
        content, lambda text: _blocks_from_text(text, slug_seen)
    )
