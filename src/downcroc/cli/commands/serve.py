from __future__ import annotations

from downcroc.runtime.paths import resolve
from downcroc.runtime.service.lifecycle import run_foreground


def run() -> None:
    run_foreground(resolve())
