from __future__ import annotations

import sys
from dataclasses import asdict

from downcroc.cli.client import CliError
from downcroc.cli.context import load
from downcroc.cli.output import json_out, record
from downcroc.runtime.config.loader import ConfigError
from downcroc.runtime.service import install as service_install
from downcroc.runtime.service.lifecycle import start, status, stop


def _show(report: dict) -> None:
    if report.get("state") == "stopped":
        record({"state": "stopped"})
        return
    record(report)


def run(args: object) -> int:
    try:
        paths, settings, _ = load()
    except ConfigError as error:
        detail = f"{error.field}: {error}" if error.field else str(error)
        print(f"config error: {detail}", file=sys.stderr)
        return 1
    if args.action == "start":
        try:
            info = start(paths, settings)
        except (OSError, RuntimeError, TimeoutError, CliError) as error:
            print(str(error), file=sys.stderr)
            return 1
        if args.json:
            json_out({**asdict(info), "url": info.base_url})
        else:
            print(f"started on {info.base_url} (pid {info.pid})")
        return 0
    if args.action == "stop":
        stopped = stop(paths, settings)
        if args.json:
            json_out({"stopped": stopped})
        else:
            print("stopped" if stopped else "downcroc was not running")
        return 0
    if args.action == "install":
        try:
            installed = service_install.install(
                paths, settings, print_only=args.print_only
            )
        except (OSError, RuntimeError) as error:
            print(str(error), file=sys.stderr)
            return 1
        if args.print_only:
            if args.json:
                json_out(installed)
            else:
                sys.stdout.write(installed["definition"])
            return 0
        if args.json:
            json_out(installed)
        else:
            print(f"installed {installed['kind']} at {installed['path']}")
        return 0
    if args.action == "uninstall":
        try:
            removed = service_install.uninstall(paths, settings)
        except (OSError, RuntimeError) as error:
            print(str(error), file=sys.stderr)
            return 1
        if args.json:
            json_out(removed)
        elif removed["removed"]:
            print(f"uninstalled {removed['kind']} at {removed['path']}")
        else:
            print(f"{removed['kind']} was not installed")
        return 0
    report = status(paths)
    if args.json:
        json_out(report)
    else:
        _show(report)
    return 0
