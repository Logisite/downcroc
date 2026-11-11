from __future__ import annotations

from downcroc.cli import paths as path_tools
from downcroc.cli.client import delete, get, post, put
from downcroc.cli.errors import CliError
from downcroc.cli.output import json_out, record, table
from downcroc.cli.ui import prompts
from downcroc.cli.ui.session import Ui


def run(client, args: object, ui: Ui) -> int:
    action = getattr(args, "followup_action", None)
    if action == "status":
        return _render(get(client, _path(args)), ui)
    if action == "declare":
        return _declare(client, args, ui)
    if action == "remove":
        return _remove(client, args, ui)
    if action == "retire":
        return _retire(client, args, ui)
    raise CliError("choose status, declare, remove, or retire", code="usage")


def _declare(client, args: object, ui: Ui) -> int:
    source = path_tools.resolve_input(args.path)
    report = put(
        client,
        f"{_path(args)}/{args.step}",
        {
            "path": str(source),
            "kind": getattr(args, "kind", None),
            "version": getattr(args, "version", None),
            "dry_run": bool(getattr(args, "dry_run", False)),
        },
    )
    return _render(report, ui, dry_run=bool(getattr(args, "dry_run", False)))


def _remove(client, args: object, ui: Ui) -> int:
    dry_run = bool(getattr(args, "dry_run", False))
    if not dry_run:
        _confirm(ui, args, f"remove follow-up step {args.step}?")
    report = delete(
        client,
        f"{_path(args)}/{args.step}",
        confirm="true" if not dry_run else None,
        version=getattr(args, "version", None),
        dry_run="true" if dry_run else None,
    )
    return _render(report, ui, dry_run=dry_run)


def _retire(client, args: object, ui: Ui) -> int:
    dry_run = bool(getattr(args, "dry_run", False))
    if not dry_run:
        _confirm(ui, args, f"retire follow-up step {args.step}?")
    report = post(
        client,
        f"{_path(args)}/{args.step}/retire",
        confirm="true" if not dry_run else None,
        version=getattr(args, "version", None),
        dry_run="true" if dry_run else None,
    )
    return _render(report, ui, dry_run=dry_run)


def _confirm(ui: Ui, args: object, question: str) -> None:
    if not prompts.confirm(
        question, ui=ui, default=False, yes_flag=bool(getattr(args, "yes", False))
    ):
        raise CliError("cancelled", code="cancelled")


def _path(args: object) -> str:
    return f"/api/batches/{args.batch_id}/followups"


def _render(report: dict, ui: Ui, *, dry_run: bool = False) -> int:
    if ui.json_mode:
        json_out(report)
        return 0
    record({"batch": report["batch_id"], "steps": len(report["steps"])})
    rows = [
        [
            item["step"],
            item["kind"],
            item["state"],
            item["after_days"],
            item["when"],
            item["counts"].get("candidates", 0),
            item["counts"].get("sent", 0),
            item["child_batch_id"] or "-",
        ]
        for item in report["steps"]
    ]
    table(
        ["step", "kind", "state", "after", "when", "candidates", "sent", "child"],
        rows,
    )
    if not rows:
        print("no follow-up steps")
    for item in report["steps"]:
        if item.get("detail"):
            print(f"{item['step']}: {item['detail']}")
    if dry_run:
        print("dry run, nothing was written")
    elif report.get("changed") and not ui.quiet:
        print(f"next: downcroc batch followups status {report['batch_id']}")
    return 0
