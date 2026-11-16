from __future__ import annotations

from downcroc.cli.install_health import probe, repair
from downcroc.cli.output import json_out
from downcroc.cli.ui.session import build


def run(args: object) -> int:
    ui = build(args)
    health = probe()
    if health.ok:
        report = health.as_dict()
    else:
        report = repair().as_dict()
    if ui.json_mode:
        json_out(report)
        return 0 if report["ok"] else 1
    label = "ok" if report["ok"] else "failed"
    print(f"managed install: {label} ({report['status']})")
    print(f"  {report['detail']}")
    if report["fix"]:
        print(f"  next: {report['fix']}")
    return 0 if report["ok"] else 1
