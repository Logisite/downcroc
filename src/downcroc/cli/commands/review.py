from __future__ import annotations

from downcroc.cli.client import api, get, post
from downcroc.cli.context import load
from downcroc.cli.errors import CliError
from downcroc.cli.output import json_out, record, table
from downcroc.cli.ui import prompts
from downcroc.cli.ui.session import Ui, build


def _pending(client) -> list[dict]:
    return get(client, "/api/batches", state="awaiting_approval", limit=100)


def _list(rows: list[dict], ui: Ui) -> None:
    if not rows:
        print("nothing is waiting for review")
        if not ui.quiet:
            print("next: downcroc send")
        return
    table(
        ["batch", "name", "messages", "sent", "failed", "created"],
        [
            [
                item["id"],
                item["name"],
                item["counts"].get("awaiting_approval", 0),
                item["counts"].get("sent", 0),
                item["counts"].get("failed", 0),
                item["created_at"],
            ]
            for item in rows
        ],
    )
    if not ui.quiet:
        print()
        print(f"next: downcroc review --batch {rows[0]['id']}")


def _detail(batch: dict) -> None:
    record(
        {
            "batch": f"{batch['id']} ({batch['name']})",
            "state": batch["state"],
            "approval": batch["approval"],
            "created_at": batch["created_at"],
            "source": batch["source_ref"],
        }
    )
    record(
        {
            "waiting": batch["counts"].get("awaiting_approval", 0),
            "sent": batch["counts"].get("sent", 0),
            "failed": batch["counts"].get("failed", 0),
        }
    )
    for sample in batch.get("samples") or []:
        print()
        print(f"{sample['email']}: {sample['subject']}")
        for line in (sample["text"] or "").splitlines()[:3]:
            print(f"  {line}")
    for warning in batch.get("warnings") or []:
        print(f"warning: {warning}")
    for field in batch.get("ignored") or []:
        print(f"ignored: {field}")


def _approve(client, batch: dict, mode: str, ui: Ui, yes: bool) -> dict:
    word = "one sample" if mode == "one" else "every remaining message"
    if not yes and not prompts.confirm(
        f"Approve and send {word} for {batch['name']}?", ui=ui, default=False
    ):
        raise CliError("cancelled", code="cancelled")
    return post(client, f"/api/batches/{batch['id']}/approve", {"mode": mode})


def _cancel(client, batch: dict, ui: Ui, yes: bool) -> dict:
    waiting = batch["counts"].get("awaiting_approval", 0)
    if not yes and not prompts.confirm(
        f"Cancel {waiting:,} waiting messages in {batch['name']}?",
        ui=ui,
        default=False,
    ):
        raise CliError("cancelled", code="cancelled")
    return post(client, f"/api/batches/{batch['id']}/cancel")


def _action(client, batch: dict, args: object, ui: Ui) -> int:
    _detail(batch)
    if batch["state"] != "awaiting_approval":
        print(f"state: {batch['state']}, approval is not available")
        return 0
    waiting = batch["counts"].get("awaiting_approval", 0)
    choice = prompts.choose(
        "What next?",
        [
            prompts.Option("Send one sample now", "one", "leaves the rest held"),
            prompts.Option(
                f"Approve the remaining {waiting:,} and send",
                "all",
                "releases every waiting message",
            ),
            prompts.Option("Cancel the batch", "cancel", "does not recall sent mail"),
        ],
        ui=ui,
        default=0,
    )
    if choice == "one":
        updated = _approve(client, batch, "one", ui, False)
        record({"approved": f"one sample of {updated['name']}"})
    elif choice == "all":
        updated = _approve(client, batch, "all", ui, False)
        record({"approved": f"{updated['name']}, {waiting:,} released"})
    elif choice == "cancel":
        updated = _cancel(client, batch, ui, False)
        record({"cancelled": updated["id"], "state": updated["state"]})
        print("mail already in flight cannot be recalled")
    else:
        return 0
    return 0


def run(args: object) -> int:
    ui = build(args)
    paths, _, _ = load()
    with api(paths, timeout=getattr(args, "timeout", None)) as client:
        batch_id = getattr(args, "batch", None)
        if batch_id:
            batch = get(client, f"/api/batches/{batch_id}")
            if ui.json_mode:
                json_out(batch)
                return 0
            if not ui.interactive:
                _detail(batch)
                return 0
            return _action(client, batch, args, ui)
        rows = _pending(client)
        if ui.json_mode:
            json_out(rows)
            return 0
        if not ui.interactive:
            _list(rows, ui)
            return 0
        if not rows:
            _list(rows, ui)
            return 0
        chosen = prompts.choose(
            "Pending review",
            [
                prompts.Option(
                    item["name"],
                    item["id"],
                    f"{item['counts'].get('awaiting_approval', 0):,} waiting",
                )
                for item in rows
            ],
            ui=ui,
            default=0,
            back=False,
        )
        batch = get(client, f"/api/batches/{chosen}")
        return _action(client, batch, args, ui)
