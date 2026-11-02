from __future__ import annotations

import shutil

from downcroc.cli.context import load
from downcroc.cli.errors import CliError
from downcroc.cli.install_layout import install_prefix, launchers, trees
from downcroc.cli.output import json_out, record
from downcroc.cli.ui.session import build
from downcroc.runtime import keyring
from downcroc.runtime.service.lifecycle import status, stop


def run(args: object) -> int:
    ui = build(args)
    prefix = install_prefix()
    if prefix is None:
        raise CliError(
            "this downcroc is not a managed install",
            code="not_managed_install",
            hint="uninstall a checkout with git, or remove the virtual environment you created",
        )
    paths, settings, _ = load()
    was_running = status(paths).get("state") == "running"
    if was_running:
        stop(paths, settings)
    removed: list[str] = []
    for launcher in launchers(prefix):
        if launcher.exists() or launcher.is_symlink():
            launcher.unlink(missing_ok=True)
            removed.append(str(launcher))
    for tree in trees(prefix):
        if tree.exists():
            shutil.rmtree(tree)
            removed.append(str(tree))
    if args.purge:
        keyring.delete(str(paths.data / "vault.enc"))
        for directory in (paths.config, paths.data, paths.state):
            if directory.exists():
                shutil.rmtree(directory)
                removed.append(str(directory))
    body = {
        "removed": removed,
        "data": "purged" if args.purge else "kept",
        "stopped": was_running,
    }
    if ui.json_mode:
        json_out(body)
        return 0
    record({"removed": len(removed), "data": body["data"]})
    for item in removed:
        print(f"  {item}")
    if not args.purge:
        print("config, data, and state were kept")
        print("use --purge to remove them as well")
    return 0
