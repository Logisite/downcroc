"""Color math for the paint layer: blending, gradients, alpha resolves."""

from __future__ import annotations

from rich.color import Color


def parse(hex_color: str) -> tuple[int, int, int]:
    """Parse a #rrggbb color into an rgb triplet."""
    color = Color.parse(hex_color)
    triplet = color.get_truecolor()
    return triplet.red, triplet.green, triplet.blue


def blend(a: str, b: str, t: float) -> str:
    """Linear interpolate two hex colors; t=0 returns a, t=1 returns b."""
    ta, ga, ba = parse(a)
    tb, gb, bb = parse(b)
    r = round(ta + (tb - ta) * t)
    g = round(ga + (gb - ga) * t)
    bl = round(ba + (bb - ba) * t)
    return f"#{r:02x}{g:02x}{bl:02x}"


def gradient(text: str, start: str, end: str) -> str:
    """Produce markup that colors ``text`` with a left-to-right gradient.

    Returns console markup string; callers that already hold Text objects
    should prefer ``stylize_span`` to avoid escaping concerns.
    """
    if not text:
        return ""
    steps = len(text)
    parts: list[str] = []
    for index, char in enumerate(text):
        if char.isspace():
            parts.append(char)
            continue
        t = index / max(steps - 1, 1)
        parts.append(f"[{blend(start, end, t)}]{char}[/]")
    return "".join(parts)


def stylize_span(text: object, start: int, end: int, a: str, b: str) -> None:
    """Apply a per-character horizontal gradient to an existing Text span.

    ``text`` must be a rich.text.Text; span positions are character offsets.
    """
    for index in range(start, min(end, len(text))):
        t = index / max(start + (end - start) - 1, 1)
        text.stylize(blend(a, b, t), index, index + 1)


def fade_block(steps: int, start: str, end: str) -> list[str]:
    """Hex colors for a glow fade, darkest first, ``steps`` entries long."""
    return [blend(end, start, step / max(steps - 1, 1)) for step in range(steps)]
