"""Startup splash: the wordmark resolves out of a field of noise."""

from __future__ import annotations

import argparse
import math
import os
import random
import select
import shutil
import sys
import time

from downcroc.cli.ui.session import Ui

RESET = "\x1b[0m"
HIDE = "\x1b[?25l"
SHOW = "\x1b[?25h"
CLEAR = "\x1b[2K"
FRAME_S = 0.04
GLOW_FRAMES = 6
FIELD_FRAMES = 40
SPEED = 0.7

DOTS = "\u00b7\u2022\u2027."
BLOCKS = "\u2591\u2592\u2593"
FULL = "\u2591\u2592\u2593\u2588\u2584\u2580"

RAMP = (
    (13, 92, 118),
    (6, 148, 178),
    (34, 211, 238),
    (165, 243, 252),
)
NOISE_RGB = (13, 78, 98)
ICE = (196, 248, 253)

FONT = {
    "d": [
        "\u2588\u2580\u2580\u2584",
        "\u2588  \u2588",
        "\u2588  \u2588",
        "\u2588  \u2588",
        "\u2580\u2580\u2580\u2580",
    ],
    "o": [
        "\u2588\u2580\u2580\u2588",
        "\u2588  \u2588",
        "\u2588  \u2588",
        "\u2588  \u2588",
        "\u2580\u2580\u2580\u2580",
    ],
    "w": [
        "\u2588   \u2588",
        "\u2588   \u2588",
        "\u2588 \u2588 \u2588",
        "\u2588\u2584\u2588\u2584\u2588",
        "\u2580   \u2580",
    ],
    "n": [
        "\u2588\u2580\u2580\u2584",
        "\u2588  \u2588",
        "\u2588  \u2588",
        "\u2588  \u2588",
        "\u2580  \u2580",
    ],
    "c": [
        "\u2588\u2580\u2580\u2580",
        "\u2588   ",
        "\u2588   ",
        "\u2588   ",
        "\u2580\u2580\u2580\u2580",
    ],
    "r": [
        "\u2588\u2580\u2580\u2584",
        "\u2588  \u2588",
        "\u2588   ",
        "\u2588   ",
        "\u2580   ",
    ],
}

WORD = "downcroc"


def _wordmark() -> list[str]:
    height = len(next(iter(FONT.values())))
    rows = [""] * height
    for index, letter in enumerate(WORD):
        for line in range(height):
            rows[line] += FONT[letter][line]
        if index != len(WORD) - 1:
            rows = [row + " " for row in rows]
    return rows


def _lerp(start: int, end: int, ratio: float) -> int:
    return round(start + (end - start) * ratio)


def _blend(low: tuple[int, int, int], high: tuple[int, int, int], ratio: float):
    ratio = min(1.0, max(0.0, ratio))
    return tuple(_lerp(low[i], high[i], ratio) for i in range(3))


def _ramp(ratio: float) -> tuple[int, int, int]:
    ratio = min(0.999, max(0.0, ratio))
    span = len(RAMP) - 1
    index = int(ratio * span)
    local = ratio * span - index
    return _blend(RAMP[index], RAMP[min(span, index + 1)], local)


def _to_256(rgb: tuple[int, int, int]) -> int:
    red, green, blue = (min(5, value * 6 // 256) for value in rgb)
    return 16 + 36 * red + 6 * green + blue


def _paint(rgb: tuple[int, int, int], mode: str, text: str) -> str:
    if mode == "none":
        return text
    if mode == "true":
        return f"\x1b[38;2;{rgb[0]};{rgb[1]};{rgb[2]}m{text}{RESET}"
    return f"\x1b[38;5;{_to_256(rgb)}m{text}{RESET}"


def _noise(seed: int) -> str:
    return FULL[random.Random(seed).randrange(len(FULL))]


def _field(rows: list[str], tick: int, heat: float) -> list[list[tuple]]:
    width = max(len(row) for row in rows)
    height = len(rows)
    centre_x = (width - 1) / 2
    centre_y = (height - 1) / 2
    grid: list[list[tuple[str, tuple[int, int, int]]]] = []
    for y in range(height):
        line: list[tuple[str, tuple[int, int, int]]] = []
        for x in range(width):
            dx = (x - centre_x) / max(1.0, centre_x)
            dy = (y - centre_y) / max(1.0, centre_y)
            if math.hypot(dx, dy) > 1.05:
                line.append((" ", (0, 0, 0)))
                continue
            wave = math.sin(x * 0.55 + y * 1.7 - tick * 0.55)
            wave += math.cos(x * 1.05 - y * 0.8 + tick * 0.4)
            value = (wave + 2.0) / 4.0 + 0.18 * heat
            if value < 0.30:
                char = " "
            elif value < 0.50:
                char = "\u00b7"
            elif value < 0.70:
                char = "\u2022"
            elif value < 0.86:
                char = "\u2591"
            else:
                char = "\u2592"
            line.append((char, _blend(NOISE_RGB, RAMP[2], min(1.0, value))))
        grid.append(line)
    return grid


def _compose(rows: list[str], resolved: int, glow: int) -> list[list[tuple]]:
    width = max(len(row) for row in rows)
    grid: list[list[tuple[str, tuple[int, int, int]]]] = []
    for y, row in enumerate(rows):
        line: list[tuple[str, tuple[int, int, int]]] = []
        for x in range(width):
            char = row[x] if x < len(row) else " "
            if char == " ":
                line.append((" ", (0, 0, 0)))
                continue
            if x < resolved:
                rgb = _ramp(x / max(1, width - 1))
                if 0 <= x - glow < 2:
                    rgb = ICE
                line.append((char, rgb))
            else:
                seed = (y + 1) * 7919 + x * 104729 + resolved * 31
                line.append((_noise(seed), NOISE_RGB))
        grid.append(line)
    return grid


def _render(grid: list[list[tuple]], mode: str, pad: int) -> list[str]:
    prefix = " " * pad
    return [
        prefix + "".join(_paint(rgb, mode, char) for char, rgb in row).rstrip()
        for row in grid
    ]


def _mode(colour: bool) -> str:
    if not colour:
        return "none"
    if os.environ.get("COLORTERM", "") in {"truecolor", "24bit"}:
        return "true"
    return "256"


def _wanted(ui: Ui) -> bool:
    if not ui.interactive or ui.quiet:
        return False
    if os.environ.get("DOWNCROC_NO_SPLASH"):
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    return ui.width >= len(_wordmark()[0])


def _key_waiting() -> bool:
    try:
        ready, _, _ = select.select([sys.stdin], [], [], 0)
    except OSError, ValueError:
        return False
    if not ready:
        return False
    try:
        sys.stdin.read(1)
    except OSError, ValueError:
        pass
    return True


def _draw(lines: list[str], height: int, first: bool) -> None:
    if not first:
        sys.stdout.write(f"\x1b[{height}A")
    for line in lines:
        sys.stdout.write(CLEAR + line + "\n")
    sys.stdout.flush()


def animate(
    mode: str,
    columns: int,
    speed: float = SPEED,
    disturbance: int = FIELD_FRAMES,
) -> None:
    rows = _wordmark()
    width = max(len(row) for row in rows)
    if columns < width:
        return
    pad = max(0, (columns - width) // 2)
    height = len(rows)
    delay = FRAME_S / max(0.1, speed)
    frames = max(0, disturbance) + width + GLOW_FRAMES
    sys.stdout.write(HIDE)
    try:
        for number in range(frames):
            if number < disturbance:
                heat = number / max(1, disturbance - 1)
                grid = _field(rows, number, heat)
            else:
                step = number - disturbance
                resolved = min(width, step + 1)
                glow = step - width if resolved >= width else -4
                grid = _compose(rows, resolved, glow)
            _draw(_render(grid, mode, pad), height, number == 0)
            if _key_waiting():
                break
            time.sleep(delay)
        _draw(_render(_compose(rows, width, -4), mode, pad), height, False)
    finally:
        sys.stdout.write(SHOW)
        sys.stdout.flush()


def play(ui: Ui) -> None:
    if not _wanted(ui):
        return
    print()
    animate(_mode(ui.colour), ui.width)
    print()
    print()
    print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="preview the downcroc splash")
    parser.add_argument("--speed", type=float, default=SPEED)
    parser.add_argument("--disturbance", type=int, default=FIELD_FRAMES)
    parser.add_argument("--static", action="store_true")
    parser.add_argument("--no-colour", action="store_true")
    parser.add_argument("--truecolour", action="store_true")
    args = parser.parse_args(argv)
    rows = _wordmark()
    columns = shutil.get_terminal_size((80, 24)).columns
    mode = "none" if args.no_colour else "true" if args.truecolour else _mode(True)
    if args.static or not sys.stdout.isatty():
        pad = max(0, (columns - len(rows[0])) // 2)
        for line in _render(_compose(rows, len(rows[0]) + 1, -4), mode, pad):
            print(line)
        return 0
    animate(mode, columns, args.speed, args.disturbance)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
