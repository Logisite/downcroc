from __future__ import annotations

from downcroc.domain.errors import ConfirmationRequired


def require(confirm: bool) -> None:
    if confirm:
        return
    raise ConfirmationRequired(
        "this action changes data and needs confirmation",
        hint="pass confirm=true to confirm in a script",
    )
