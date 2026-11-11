from __future__ import annotations

import base64
import os
import shutil
import subprocess
import sys


def copy(text: str) -> bool:
    for command in _commands():
        try:
            process = subprocess.run(
                command,
                input=text.encode(),
                check=False,
                capture_output=True,
            )
        except OSError:
            continue
        if process.returncode == 0:
            return True
    return bool(_osc52(text))


def _commands() -> list[list[str]]:
    if os.name == "nt":
        return [["clip"]]
    found = []
    for name, args in (
        ("wl-copy", ["wl-copy"]),
        ("xclip", ["xclip", "-selection", "clipboard"]),
        ("xsel", ["xsel", "--clipboard", "--input"]),
        ("pbcopy", ["pbcopy"]),
    ):
        path = shutil.which(name)
        if path:
            found.append([path, *args[1:]])
    return found


def _osc52(text: str) -> bool:
    if not sys.stdout.isatty() or os.environ.get("TERM") == "dumb":
        return False
    encoded = base64.b64encode(text.encode()).decode()
    try:
        sys.stdout.write(f"\033]52;c;{encoded}\a")
        sys.stdout.flush()
    except OSError:
        return False
    return True
