from __future__ import annotations

from pathlib import Path

from downcroc.cli.docs.content.index import build_index
from downcroc.cli.docs.content.parser import parse_document


def test_parse_document_headings_and_blocks() -> None:
    src = """---
title: Sample
description: desc
---
# Title

Paragraph with **bold**, `code`, and [[target|label]].

!!! note "Heads up"
    Callout body

- one
- two

```python
print('hi')
```

| a | b |
| - | - |
| 1 | 2 |
"""
    doc = parse_document(src)
    assert doc.title == "Sample"
    assert doc.description == "desc"
    kinds = [b.kind for b in doc.blocks]
    assert "heading" in kinds
    assert "paragraph" in kinds
    assert "callout" in kinds
    assert "list" in kinds
    assert "code" in kinds
    assert "table" in kinds
    assert doc.headings[0].slug == "title"
    callouts = [b for b in doc.blocks if b.kind == "callout"]
    assert callouts and callouts[0].title == "Heads up"


def test_build_index_on_packaged_docs() -> None:
    root = Path("src/downcroc/docs")
    idx = build_index(root)
    assert len(idx.pages) > 0
    page = idx.get("index")
    assert page is not None
    assert page.title
    assert any(h.text for h in page.headings)
    prev, nxt = idx.prev_next(page.route)
    assert prev is None or prev.rel
    assert nxt is None or nxt.rel
