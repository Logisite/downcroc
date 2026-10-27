from __future__ import annotations

import os
import shlex
import shutil
import sys
from dataclasses import dataclass

GLYPHS = {
    "nerd": {
        "selected": "\uf054",
        "unselected": " ",
        "pointer": "\u25c6",
        "choice": "\uf111",
        "checked": "\uf00c",
        "unchecked": "\uf096",
        "back": "\uf060",
        "search": "\uf002",
        "dot": "\uf111",
        "ok": "\uf00c",
        "fail": "\uf00d",
        "warning": "\uf071",
        "folder": "\uf07b",
        "file": "\uf15b",
        "mail": "\uf0e0",
        "clock": "\uf017",
        "lock": "\uf023",
        "key": "\uf084",
        "arrow": "\uf061",
    },
    "ascii": {
        "selected": ">",
        "unselected": " ",
        "pointer": ">",
        "choice": "*",
        "checked": "[x]",
        "unchecked": "[ ]",
        "back": "<",
        "search": "/",
        "dot": ".",
        "ok": "[ok]",
        "fail": "[fail]",
        "warning": "!",
        "folder": "[dir]",
        "file": "[file]",
        "mail": "@",
        "clock": "[time]",
        "lock": "[lock]",
        "key": "[key]",
        "arrow": "->",
    },
}

RESET = "\033[0m"
TONE = {
    "good": "\033[32m",
    "bad": "\033[31m",
    "warn": "\033[33m",
    "accent": "\033[36m",
    "muted": "\033[2m",
    "title": "\033[1m",
    "key": "\033[1;36m",
}

DEFAULT_TIMEOUT_S = 10.0


@dataclass(frozen=True)
class Ui:
    interactive: bool
    json_mode: bool
    glyphs: str
    colour: bool
    wide: bool
    full: bool
    quiet: bool
    timeout: float
    width: int

    def glyph(self, name: str) -> str:
        return GLYPHS[self.glyphs].get(name, "")

    def paint(self, text: str, tone: str) -> str:
        if not self.colour or tone not in TONE:
            return text
        return f"{TONE[tone]}{text}{RESET}"

    def bold(self, text: str) -> str:
        return self.paint(text, "title")

    def dim(self, text: str) -> str:
        return self.paint(text, "muted")

    def accent(self, text: str) -> str:
        return self.paint(text, "accent")

    def heading(self, text: str) -> str:
        return f"{self.glyph('pointer')} {self.bold(self.accent(text))}"

    def result(self, ok: bool, word: str, detail: str = "") -> str:
        tone = "good" if ok else "bad"
        tag = self.paint(f"{self.glyph('ok' if ok else 'fail')} {word}", tone)
        return f"{tag}    {detail}".rstrip()


def _flag(args: object, name: str) -> object:
    return getattr(args, name, None)


def _config_glyphs() -> str:
    from downcroc.runtime.config.loader import ConfigError, read
    from downcroc.runtime.paths import resolve

    try:
        settings = read(resolve().config_file)
    except ConfigError, OSError:
        return "auto"
    return settings.cli.glyphs


def _glyph_choice(args: object) -> str:
    value = _flag(args, "glyphs") or os.environ.get("DOWNCROC_GLYPHS")
    if not value or value == "auto":
        value = _config_glyphs()
    return "nerd" if str(value) == "nerd" else "ascii"


def _timeout(args: object) -> float:
    value = _flag(args, "timeout")
    if value is None:
        value = os.environ.get("DOWNCROC_TIMEOUT")
    try:
        return float(value) if value is not None else DEFAULT_TIMEOUT_S
    except TypeError, ValueError:
        return DEFAULT_TIMEOUT_S


def colour_allowed(args: object) -> bool:
    choice = _flag(args, "color") or "auto"
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    if choice == "never":
        return False
    if choice == "always":
        return True
    return sys.stdout.isatty()


def build(args: object) -> Ui:
    json_mode = bool(_flag(args, "json"))
    no_input = bool(_flag(args, "no_input")) or bool(
        os.environ.get("DOWNCROC_NO_INPUT")
    )
    interactive = (
        sys.stdin.isatty()
        and sys.stdout.isatty()
        and not json_mode
        and not no_input
        and not os.environ.get("CI")
    )
    columns = shutil.get_terminal_size((100, 24)).columns
    width = columns if _flag(args, "wide") else min(columns, 120)
    return Ui(
        interactive=interactive,
        json_mode=json_mode,
        glyphs=_glyph_choice(args),
        colour=colour_allowed(args),
        wide=bool(_flag(args, "wide")),
        full=bool(_flag(args, "full")),
        quiet=bool(_flag(args, "quiet")),
        timeout=_timeout(args),
        width=max(40, width),
    )


def pager_enabled(args: object) -> bool:
    if _flag(args, "no_pager") or os.environ.get("NO_PAGER"):
        return False
    return sys.stdout.isatty() and not bool(_flag(args, "json"))


def editor() -> tuple[list[str], str]:
    for name in ("VISUAL", "EDITOR"):
        value = os.environ.get(name)
        if value:
            parts = shlex.split(value)
            return (parts, parts[0])
    for fallback in ("nano", "vi"):
        found = shutil.which(fallback)
        if found:
            return ([found], fallback)
    return ([], "")
