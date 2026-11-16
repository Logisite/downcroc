"""Design screenshot loop: export the brick gallery, convert, and copy out.

Run from the repo root:

    uv run python scripts/design/shot.py            # PNG + SVG to the outbox
    uv run python scripts/design/shot.py --width 1100
    uv run python scripts/design/shot.py --out /tmp/nowhere

The PNG is the review artifact; it lands in the outbox (default
/mnt/sdcard/Downloads) and stays in /tmp/opencode for the session.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

SVG_TMP = Path("/tmp/opencode/design-gallery.svg")
PNG_TMP = Path("/tmp/opencode/design-gallery.png")
DEFAULT_OUT = Path("/mnt/sdcard/Downloads")

_TEXT = re.compile(r"<text ([^>]*?)>(.*?)</text>", re.DOTALL)
_ATTR = re.compile(r'([\w-]+)="([^"]*)"')


def _flatten_svg(svg: str) -> str:
    """Anchor every glyph at its exact cell position.

    cairosvg ignores textLength, so multi-glyph runs drift by font advance
    and borders stop meeting corners. Rewriting each run as one <text> per
    cell makes glyph positions independent of font metrics.
    """

    def replace(match: re.Match[str]) -> str:
        attrs = dict(_ATTR.findall(match.group(1)))
        content = match.group(2)
        if "textLength" not in attrs:
            return match.group(0)
        try:
            start_x = float(attrs["x"])
            y = attrs["y"]
            klass = attrs.get("class", "")
            clip = attrs.get("clip-path", "")
            length = float(attrs["textLength"].split()[0])
        except KeyError, ValueError:
            return match.group(0)
        tokens = re.findall(r"&#\d+;|&\w+;|.", content)
        if not tokens:
            return match.group(0)
        step = length / len(tokens)
        parts = []
        for index, token in enumerate(tokens):
            x = start_x + index * step
            if token == "&":
                token = "&amp;"
            elif token == "<":
                token = "&lt;"
            elif token == ">":
                token = "&gt;"
            parts.append(
                f'<text x="{x:.1f}" y="{y}" class="{klass}" '
                f'clip-path="{clip}">{token}</text>'
            )
        return "".join(parts)

    return _TEXT.sub(replace, svg)


def export_gallery(svg_path: Path) -> None:
    """Render the gallery to an SVG via the design package."""
    from downcroc.cli.design.gallery import export_gallery_svg

    export_gallery_svg(str(svg_path))
    svg_path.write_text(_flatten_svg(svg_path.read_text()), encoding="utf-8")


def svg_to_png(svg_path: Path, png_path: Path, width: int) -> None:
    """Convert the SVG to a PNG with cairosvg on a pure black background."""
    import cairosvg

    cairosvg.svg2png(
        url=str(svg_path),
        write_to=str(png_path),
        output_width=width,
        background_color="#000000",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--width", type=int, default=900, help="PNG pixel width")
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="outbox directory for the PNG and SVG",
    )
    parser.add_argument(
        "--zoom",
        nargs=4,
        type=int,
        metavar=("X", "Y", "W", "H"),
        help="also save a 2x zoom crop of the PNG region for edge review",
    )
    args = parser.parse_args()

    export_gallery(SVG_TMP)
    svg_to_png(SVG_TMP, PNG_TMP, args.width)

    if args.zoom:
        from PIL import Image

        x, y, w, h = args.zoom
        img = Image.open(PNG_TMP)
        img.resize((img.width * 2, img.height * 2), Image.LANCZOS).crop(
            (x * 2, y * 2, (x + w) * 2, (y + h) * 2)
        ).save(PNG_TMP.with_name("design-zoom.png"))

    args.out.mkdir(parents=True, exist_ok=True)
    copies = [SVG_TMP, PNG_TMP]
    zoomed = PNG_TMP.with_name("design-zoom.png")
    if args.zoom and zoomed.is_file():
        copies.append(zoomed)
    for source in copies:
        shutil.copy2(source, args.out / source.name)
    print(f"copied {[p.name for p in copies]} to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
