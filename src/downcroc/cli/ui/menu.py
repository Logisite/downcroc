from __future__ import annotations

from downcroc.cli.errors import Cancelled, CliError, render
from downcroc.cli.ui.session import Ui

MENUS = {
    "home_menu": (),
    "accounts_menu": ("account",),
    "providers_menu": ("provider",),
    "batch_menu": ("batch",),
    "job_menu": ("job",),
    "template_menu": ("template",),
    "vault_menu": ("vault",),
    "config_menu": ("config",),
    "config_set": ("config", "set"),
    "failed_menu": ("failed",),
    "mail_menu": ("mail",),
    "service_menu": ("service",),
}


def ui_flags(ui: Ui) -> list[str]:
    flags = ["--glyphs", ui.glyphs, "--color", "always" if ui.colour else "never"]
    if ui.wide:
        flags.append("--wide")
    if ui.full:
        flags.append("--full")
    if ui.quiet:
        flags.append("--quiet")
    if ui.json_mode:
        flags.append("--json")
    if not ui.interactive:
        flags.append("--no-input")
    return flags


def run_args(ui: Ui, *argv: str) -> int:
    from downcroc.cli import dispatch

    try:
        return dispatch.run([*argv, *ui_flags(ui)])
    except CliError as error:
        render(error, json_mode=ui.json_mode)
        return error.exit_code
    except Cancelled:
        print(ui.dim("cancelled"))
        return 1


def open_menu(ui: Ui, name: str) -> bool:
    """Open the interactive tree at a named command family."""
    path = MENUS.get(name)
    if path is None:
        return False
    from downcroc.cli.ui.tree import open_path

    return open_path(ui, path)


def count_label(count: int, noun: str) -> str:
    suffix = "" if count == 1 else "s"
    return f"{count:,} {noun}{suffix}"
