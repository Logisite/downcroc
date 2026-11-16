"""Design system bricks: golden-image and color tests.

The snapshot is the design gate: if a token or paint call drifts, the
screenshot diff catches it. Color math is verified directly since it is pure.
"""

from __future__ import annotations

import pytest
from syrupy.extensions.image import PNGImageSnapshotExtension  # noqa: F401

from downcroc.cli.design.gallery import (
    export_gallery_plain_text,
    export_gallery_text,
)
from downcroc.cli.design.paint.color import blend, gradient
from downcroc.cli.design.playground import PlaygroundApp

pytestmark = pytest.mark.usefixtures("snap_compare")


def test_blend_interpolates() -> None:
    assert blend("#000000", "#ffffff", 0.5) == "#808080"
    assert blend("#0b0e14", "#0b0e14", 0.7) == "#0b0e14"


def test_gradient_colors_each_glyph() -> None:
    out = gradient("ab", "#000000", "#ffffff")
    assert "#000000" in out and "#ffffff" in out


def test_gallery_text_renders_bricks() -> None:
    text = export_gallery_text()
    assert "downcroc design system" in text
    assert "watcher" in text
    assert "enter" in text
    assert "BUTTON STATES (PRIMARY)" in text
    assert "CALLOUT TONES" in text
    assert "NAV ITEMS / STATES" in text
    assert "No data yet" in text
    assert "disabled copy state" in text
    assert "copied state" in text
    assert "Figure: compact inset panel sample" in text


def test_gallery_plain_text_snapshot(snapshot) -> None:
    """Stable text snapshot of the full gallery structure/content."""
    assert export_gallery_plain_text() == snapshot


@pytest.mark.parametrize("path_to_cli", [[], None])
def test_playground_snapshot(snap_compare: object, path_to_cli: list) -> None:
    assert snap_compare(PlaygroundApp(), terminal_size=(90, 22))
