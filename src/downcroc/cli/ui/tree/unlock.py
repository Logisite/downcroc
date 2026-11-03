from __future__ import annotations

from downcroc.cli.errors import Cancelled, CliError
from downcroc.cli.ui import prompts
from downcroc.cli.ui.session import Ui


def is_locked(code: str | None, message: str) -> bool:
    return code == "vault_locked" or "vault is locked" in message.casefold()


def offer(ui: Ui) -> bool | None:
    try:
        wanted = prompts.confirm(
            "The vault is locked. Unlock it now?",
            ui=ui,
            default=True,
        )
    except Cancelled:
        return None
    if not wanted:
        return None
    from downcroc.cli.commands import vault

    try:
        vault.unlock_now()
    except Cancelled:
        print(ui.dim("cancelled"))
        return False
    except CliError as error:
        print(ui.result(False, error.label))
        if error.hint:
            print(f"  hint: {error.hint}")
        return False
    return True
