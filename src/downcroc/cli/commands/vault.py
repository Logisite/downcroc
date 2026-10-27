from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from downcroc.cli import paths as path_tools
from downcroc.cli.client import api, get, post
from downcroc.cli.context import load
from downcroc.cli.errors import CliError, no_terminal
from downcroc.cli.output import json_out, record
from downcroc.cli.ui import prompts
from downcroc.cli.ui.menu import open_menu
from downcroc.cli.ui.session import Ui, build
from downcroc.runtime import keyring


def vault_path() -> str:
    paths, _, _ = load()
    return str((paths.data / "vault.enc").absolute())


def _unavailable(store_required: bool) -> CliError:
    if store_required:
        return CliError(
            "the system credential store is unavailable",
            code="keyring_unavailable",
            hint="run without --keyring and type the password instead",
        )
    return CliError(
        "the system credential store is unavailable",
        code="keyring_unavailable",
    )


def _from_flags(args: object) -> tuple[str, bool] | None:
    if getattr(args, "password_stdin", False):
        return path_tools.read_secret_stdin(), False
    path = getattr(args, "password_file", None)
    if path:
        return path_tools.read_secret(path), False
    return None


def password(args: object, ui: Ui, *, confirm: bool = False) -> tuple[str, bool]:
    supplied = _from_flags(args)
    if supplied is not None:
        return supplied
    if not getattr(args, "no_keyring", False):
        stored = keyring.get(vault_path())
        if stored:
            return stored, True
    if getattr(args, "keyring", False):
        raise _unavailable(store_required=True)
    if not sys.stdin.isatty():
        raise no_terminal()
    first = prompts.ask_secret("Vault password", ui=ui)
    if confirm:
        again = prompts.ask_secret("Again", ui=ui)
        if again != first:
            raise CliError("the passwords do not match", code="input_invalid")
    return first, False


def _store(args: object, password_value: str, used_store: bool) -> None:
    if getattr(args, "no_keyring", False) or used_store:
        return
    if keyring.set_password(vault_path(), password_value):
        ui = build(args)
        if ui.interactive:
            print(f"keyring    on ({keyring.describe().name})")


def _data(args: object) -> dict:
    paths, _, _ = load()
    with api(paths, timeout=60.0) as client:
        return get(client, "/api/vault")


def _show(data: dict, args: object) -> None:
    ui = build(args)
    if ui.json_mode:
        del data["accounts"]
        json_out(data)
        return
    record(
        {
            "state": data["state"],
            "path": data["path"],
            "unlocked_at": data["unlocked_at"],
        }
    )
    if data["state"] == "locked":
        record(
            {
                "attempts_left": data["attempts_left"],
                "retry_after_s": data["retry_after_s"],
            }
        )


def _init(args: object) -> int:
    ui = build(args)
    current = _data(args)
    if Path(current["path"]).exists():
        raise CliError(
            "a vault already exists",
            code="vault_exists",
            hint="run downcroc vault unlock",
        )
    value, used_store = password(args, ui, confirm=True)
    paths, _, _ = load()
    with api(paths, timeout=60.0) as client:
        data = post(client, "/api/vault/init", {"password": value})
    _store(args, value, used_store)
    _show(data, args)
    if ui.interactive and not ui.quiet:
        print("next: downcroc account add --provider gmail --address you@example.com")
    return 0


def _unlock(args: object) -> int:
    ui = build(args)
    current = _data(args)
    if current["state"] == "unlocked":
        if ui.json_mode:
            json_out({"state": "unlocked", "changed": False})
        else:
            record({"state": "unlocked", "changed": False})
        return 0
    value, used_store = password(args, ui)
    paths, _, _ = load()
    try:
        with api(paths, timeout=60.0) as client:
            data = post(client, "/api/vault/unlock", {"password": value})
    except CliError:
        if used_store:
            keyring.delete(vault_path())
        raise
    _store(args, value, used_store)
    if ui.json_mode:
        del data["accounts"]
        json_out(data)
        return 0
    record({"state": data["state"], "changed": True})
    if used_store:
        print("vault      unlocked (system credential store)")
    return 0


def _lock(args: object) -> int:
    paths, _, _ = load()
    with api(paths, timeout=30.0) as client:
        data = post(client, "/api/vault/lock")
    forgotten = False
    if getattr(args, "forget", False):
        forgotten = keyring.delete(vault_path())
    ui = build(args)
    if ui.json_mode:
        json_out({"state": data["state"], "forgot": forgotten})
        return 0
    record({"state": data["state"]})
    if getattr(args, "forget", False):
        print("the stored password was deleted; the master password is unchanged")
        print("next: downcroc vault keyring enable")
    return 0


def _keyring(args: object) -> int:
    ui = build(args)
    action = args.action
    store = keyring.describe()
    if action == "status":
        if ui.json_mode:
            json_out(
                {
                    "available": store.available,
                    "name": store.name,
                    "reason": store.reason,
                }
            )
        else:
            record({"keyring": keyring.status()})
            if not store.available and store.reason:
                print(f"reason     {store.reason}")
        return 0
    if not store.available:
        raise _unavailable(store_required=True)
    if action == "enable":
        value, used_store = password(args, ui, confirm=False)
        del used_store
        if not keyring.set_password(vault_path(), value):
            raise _unavailable(store_required=True)
        if ui.json_mode:
            json_out({"keyring": True, "name": store.name})
        else:
            record({"keyring": f"on ({store.name})"})
        return 0
    removed = keyring.delete(vault_path())
    if ui.json_mode:
        json_out({"keyring": False, "removed": removed})
    else:
        record({"keyring": "off"})
        print("unlocking will prompt for the master password again")
    return 0


def run(args: object) -> int:
    action = getattr(args, "action", None)
    if action is None:
        ui = build(args)
        if open_menu(ui, "vault_menu"):
            return 0
        raise CliError("vault needs an action", code="usage", exit_code=2)
    if action == "status":
        _show(_data(args), args)
        return 0
    if action == "init":
        return _init(args)
    if action == "unlock":
        return _unlock(args)
    if action == "lock":
        return _lock(args)
    return _keyring(args)


def unlock_now(args: object | None = None) -> int:
    if args is None:
        args = SimpleNamespace(
            action="unlock",
            password_stdin=False,
            password_file=None,
            keyring=False,
            no_keyring=False,
            json=False,
        )
    return _unlock(args)
