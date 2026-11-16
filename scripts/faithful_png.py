#!/usr/bin/env python3
"""Render the docs TUI to a faithful PNG from live compositor strips.

Textual's export_screenshot() SVG loses inter-run spacing when converted
by cairosvg, producing garbled images that do not match the real terminal.
This script uses app.screen._compositor.render_strips() (the actual cells a
terminal would paint) and composes a monospace SVG with per-segment
colors, then converts it to PNG.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from xml.sax.saxutils import escape


def _color_hex(color) -> str | None:
    """Best-effort true-color hex from a rich Color, else None."""
    try:
        rgb = color.get_truecolor()
    except Exception:
        return None
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def _strip_svg(strips, cell_w: int, cell_h: int, default_bg: str) -> list[str]:
    parts: list[str] = [
        f'<rect width="100%" height="100%" fill="{default_bg}"/>',
        "<style>.m{font-family:'DejaVu Sans Mono',monospace;"
        f"font-size:{cell_h - 3}px;font-kerning:none}}</style>",
    ]
    for y, strip in enumerate(strips):
        x = 0
        for seg in strip._segments:
            text = seg.text
            style = seg.style
            fg = None
            bg = None
            bold = False
            if style is not None:
                try:
                    fg = _color_hex(style.color)
                    bg = _color_hex(style.bgcolor)
                    bold = bool(style.bold)
                except AttributeError:
                    pass
            if bg and bg != default_bg and text.strip():
                parts.append(
                    f'<rect x="{x * cell_w}" y="{y * cell_h}" '
                    f'width="{len(text) * cell_w}" height="{cell_h}" fill="{bg}"/>'
                )
            if text.strip():
                bold_attr = ' font-weight="bold"' if bold else ""
                span = f"<tspan{bold_attr}>{escape(text)}</tspan>"
                parts.append(
                    f'<text class="m" x="{x * cell_w}" y="{(y + 1) * cell_h - 4}" '
                    f'xml:space="preserve" fill="{fg or "#e6edf3"}">{span}</text>'
                )
            x += len(text)
    return parts


def strips_to_svg(strips, cell_w: int = 8, cell_h: int = 16) -> str:
    width = max((s.cell_length for s in strips), default=0)
    height = len(strips)
    body = "\n".join(_strip_svg(strips, cell_w, cell_h, "#000000"))
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width * cell_w}" height="{height * cell_h}">\n{body}\n</svg>'
    )


async def capture(
    docs: Path,
    size: tuple[int, int],
    route: str | None,
    clicks: list[str],
    presses: list[str],
) -> list:
    from downcroc.cli.docs.app import DocsApp
    from downcroc.cli.docs.content.index import build_index

    idx = build_index(docs)
    app = DocsApp(idx.pages)
    async with app.run_test(size=size) as pilot:
        await pilot.pause()
        if route:
            app.action_open_link(route)
            await pilot.pause()
        for selector in clicks:
            await pilot.click(app.query_one(selector))
            await pilot.pause()
        for key in presses:
            await pilot.press(key)
            await pilot.pause()
        await pilot.pause(0.2)
        return app.screen._compositor.render_strips()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--docs", default="src/downcroc/docs")
    parser.add_argument("--size", default="140x40")
    parser.add_argument(
        "--route",
        help="open this internal route/anchor before capture (e.g. 'index')",
    )
    parser.add_argument(
        "--click",
        action="append",
        default=[],
        help="CSS selector to click before capture; repeatable",
    )
    parser.add_argument(
        "--press",
        action="append",
        default=[],
        help="key to press before capture; repeatable",
    )
    parser.add_argument("--svg", default="/tmp/opencode/faithful.svg")
    parser.add_argument("--png", default="/tmp/opencode/faithful.png")
    parser.add_argument("--cell", default="8x16")
    args = parser.parse_args()

    w_s, h_s = args.size.lower().split("x", 1)
    cw_s, ch_s = args.cell.lower().split("x", 1)
    strips = asyncio.run(
        capture(
            Path(args.docs),
            (int(w_s), int(h_s)),
            args.route,
            args.click,
            args.press,
        )
    )
    Path(args.svg).write_text(strips_to_svg(strips, int(cw_s), int(ch_s)))

    import cairosvg

    cairosvg.svg2png(url=args.svg, write_to=args.png, output_width=int(w_s) * 8 * 2)
    print(f"wrote {args.svg} and {args.png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
