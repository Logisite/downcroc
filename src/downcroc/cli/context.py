from __future__ import annotations

from downcroc.runtime.config.loader import load_or_create
from downcroc.runtime.config.schema import Settings
from downcroc.runtime.paths import Paths, ensure, resolve


def load() -> tuple[Paths, Settings, bool]:
    paths = resolve()
    ensure(paths)
    return (paths, *load_or_create(paths.config_file))
