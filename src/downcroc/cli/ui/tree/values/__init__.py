from __future__ import annotations

from downcroc.cli.ui.tree.values import (  # noqa: F401
    accounts,
    config,
    mail,
    providers,
    system,
    work,
)
from downcroc.cli.ui.tree.values.registry import (
    Named,
    fetch,
    fetch_one,
    has_resolver,
    match,
    resolve,
)

__all__ = [
    "Named",
    "fetch",
    "fetch_one",
    "has_resolver",
    "match",
    "resolve",
]
