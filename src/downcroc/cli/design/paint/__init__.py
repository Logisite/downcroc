"""The paint layer: cell buffers and color math."""

from downcroc.cli.design.paint.canvas import CanvasRenderable, CellCanvas, paint_card
from downcroc.cli.design.paint.color import blend, fade_block, gradient

__all__ = [
    "CanvasRenderable",
    "CellCanvas",
    "blend",
    "fade_block",
    "gradient",
    "paint_card",
]
