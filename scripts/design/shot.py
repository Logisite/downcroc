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
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

SVG_TMP = Path("/tmp/opencode/design-gallery.svg")
PNG_TMP = Path("/tmp/opencode/design-gallery.png")
DEFAULT_OUT = Path("/mnt/sdcard/Downloads")


def export_gallery(svg_path: Path) -> None:
    """Render the gallery to an SVG via the design package."""
    from downcroc.cli.design.gallery import export_gallery_svg

    export_gallery_svg(str(svg_path))


def svg_to_png(svg_path: Path, png_path: Path, width: int) -> None:
    """Convert the SVG to a PNG with cairosvg on a pure black background."""
    code = (
        "import cairosvg; "
        f"cairosvg.svg2png(url='{svg_path}', write_to='{png_path}', "
        f"output_width={width}, background_color='#000000')"
    )
    process = subprocess.run(
        ["uv", "run", "--with", "cairosvg", "python", "-c", code],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    if process.returncode != 0:
        sys.stderr.write(process.stderr)
        raise SystemExit(process.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--width", type=int, default=900, help="PNG pixel width")
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="outbox directory for the PNG and SVG",
    )
    args = parser.parse_args()

    export_gallery(SVG_TMP)
    svg_to_png(SVG_TMP, PNG_TMP, args.width)

    args.out.mkdir(parents=True, exist_ok=True)
    for source in (SVG_TMP, PNG_TMP):
        shutil.copy2(source, args.out / source.name)
    print(f"copied {SVG_TMP.name} and {PNG_TMP.name} to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
