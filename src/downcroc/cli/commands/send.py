from __future__ import annotations

import re
import shutil
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from downcroc.cli import inputs
from downcroc.cli import paths as path_tools
from downcroc.cli.client import api, get, post
from downcroc.cli.commands.batch_view import show_preview, show_validation
from downcroc.cli.commands.when import show_capacity
from downcroc.cli.context import load
from downcroc.cli.errors import CliError
from downcroc.cli.output import json_out, record
from downcroc.cli.ui import prompts
from downcroc.cli.ui.session import Ui, build
from downcroc.runtime.config.schema import Settings
from downcroc.runtime.paths import Paths

KINDS = (
    ("file", "A campaign file (JSON)", "a JSON campaign you already have"),
    ("csv", "A CSV plus a template", "one template, one row per recipient"),
    ("compose", "One message, composed here", "written to a reusable draft"),
)

BODY_HEADER = """# Write the message body below this line.
# Lines starting with # are removed when the draft is saved.
# Save and close the editor to continue.

"""


def _kind(path: Path, settings: Settings) -> str:
    return inputs.kind_of(path, settings)


def _templates(paths: Paths) -> list[str]:
    root = paths.templates
    if not root.is_dir():
        return []
    return sorted(
        child.name
        for child in root.iterdir()
        if child.is_dir() and (child / "template.toml").is_file()
    )


def _pick_template(paths: Paths, ui: Ui) -> str | None:
    names = _templates(paths)
    if not names:
        if not ui.interactive:
            return None
        create = prompts.confirm(
            "No template exists yet. Create one now?", ui=ui, default=True
        )
        if not create:
            return None
        name = prompts.ask("Template name", ui=ui, default="intro")
        from downcroc.cli.commands import templates as templates_command

        templates_command.run(SimpleNamespace(action="new", name=name, **ui_flags(ui)))
        names = _templates(paths)
    if not names:
        return None
    if not ui.interactive:
        return names[0] if len(names) == 1 else None
    return str(
        prompts.choose(
            "Template",
            [prompts.Option(name, name) for name in names],
            ui=ui,
            default=0,
            back=False,
        )
    )


def ui_flags(ui: Ui) -> dict:
    return {
        "json": ui.json_mode,
        "no_input": not ui.interactive,
        "yes": False,
        "wide": ui.wide,
        "full": ui.full,
        "glyphs": ui.glyphs,
        "color": "always" if ui.colour else "never",
        "quiet": ui.quiet,
        "timeout": ui.timeout,
        "no_pager": True,
    }


def _choose_source(args: object, paths: Paths, settings: Settings, ui: Ui) -> tuple:
    if getattr(args, "path", None):
        path = path_tools.resolve_input(args.path)
        template = getattr(args, "template", None)
        if template is None and _kind(path, settings) == "csv" and ui.interactive:
            template = _pick_template(paths, ui)
        return path, template, None
    if not ui.interactive:
        raise CliError(
            "a campaign file is required",
            code="usage",
            hint="pass a file, or run `downcroc send` on a terminal",
            exit_code=2,
        )
    kind = prompts.choose(
        "Send",
        [prompts.Option(label, key, detail) for key, label, detail in KINDS],
        ui=ui,
        default=0,
        back=False,
    )
    if kind == "compose":
        return None, None, None
    raw = prompts.ask("File", ui=ui, field="FILE")
    path = path_tools.resolve_input(raw)
    template = getattr(args, "template", None)
    if _kind(path, settings) == "csv" and template is None:
        template = _pick_template(paths, ui)
    return path, template, None


def _compose(paths: Paths, ui: Ui) -> tuple:
    to = prompts.ask("To", ui=ui, field="--to")
    name = prompts.ask("Name", ui=ui, required=False)
    subject = prompts.ask("Subject", ui=ui, field="--subject")
    body = prompts.open_editor(BODY_HEADER, ui=ui, suffix=".txt")
    text = "\n".join(
        line for line in body.splitlines() if not line.startswith("#")
    ).strip()
    if not text:
        raise CliError("the message body is empty", code="input_invalid")
    draft = _draft_dir(paths, subject)
    assets = draft / "assets"
    attachments = []
    while True:
        raw = prompts.ask("Attachment path, blank to finish", ui=ui, required=False)
        if not raw:
            break
        source = path_tools.resolve_input(raw, field="attachment")
        assets.mkdir(parents=True, exist_ok=True)
        target = assets / source.name
        shutil.copyfile(source, target)
        attachments.append(f"assets/{target.name}")
    target = _write_campaign(draft, to, name, subject, text, attachments)
    record({"draft": str(target)})
    if not ui.quiet:
        print("edit it, then re-run: downcroc send " + str(target))
    return target, None, target


def _draft_dir(paths: Paths, subject: str) -> Path:
    slug = _slug(subject)
    root = paths.data / "drafts"
    candidate = root / f"{date.today().isoformat()}-{slug}"
    index = 2
    while candidate.exists():
        candidate = root / f"{date.today().isoformat()}-{slug}-{index}"
        index += 1
    candidate.mkdir(parents=True)
    return candidate


def _slug(subject: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", subject.casefold()).strip("-")
    return (text[:40] or "message").strip("-")


def _write_campaign(
    draft: Path,
    to: str,
    name: str,
    subject: str,
    text: str,
    attachments: list[str],
) -> Path:
    import json

    recipient: dict = {"email": to}
    if name:
        recipient["name"] = name
    message: dict = {"key": "m1", "to": recipient, "subject": subject, "text": text}
    if attachments:
        message["attachments"] = attachments
    document = {
        "schema": "downcroc.campaign/v1",
        "producer": {"name": "downcroc-compose", "version": "1"},
        "campaign": {
            "key": draft.name,
            "name": subject,
            "routing": {"mode": "auto"},
            "options": {"approval": "review"},
        },
        "messages": [message],
        "followups": [],
    }
    target = draft / "campaign.json"
    target.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return target


def _choose_account(client, args: object, ui: Ui) -> str | None:
    if getattr(args, "account", None):
        return args.account
    if not ui.interactive:
        return None
    rows = [
        item for item in get(client, "/api/accounts") if item["status"] == "connected"
    ]
    if not rows:
        raise CliError(
            "no account is connected",
            code="account_unavailable",
            hint="run downcroc account add, then connect it",
        )
    options = [
        prompts.Option("Auto", None, "use the campaign routing policy"),
    ]
    options.extend(
        prompts.Option(item["address"], item["id"], item["provider"]) for item in rows
    )
    chosen = prompts.choose("Which account sends?", options, ui=ui, default=0)
    return chosen if isinstance(chosen, str) else None


def _approval(args: object, ui: Ui) -> str:
    flag = getattr(args, "approve", "none") or "none"
    if not ui.interactive or flag == "all":
        return flag
    return str(
        prompts.choose(
            "Approval",
            [
                prompts.Option("Hold everything for review", "none", "default"),
                prompts.Option(
                    "Send as soon as it is due",
                    "all",
                    "sends without a second look",
                ),
            ],
            ui=ui,
            default=0,
            back=False,
        )
    )


def _validate(path: Path, template: str | None, settings, paths, ui: Ui) -> dict:
    body = inputs.validate(path, template, settings, paths)
    while not body["ok"] and ui.interactive:
        show_validation(body)
        edit = prompts.confirm("Open the file in $EDITOR?", ui=ui, default=True)
        if not edit:
            break
        edited = prompts.open_editor(
            path.read_text(encoding="utf-8"), ui=ui, suffix=path.suffix
        )
        path.write_text(edited, encoding="utf-8")
        body = inputs.validate(path, template, settings, paths)
    return body


def _preview(client, path: Path, template: str | None, account: str | None) -> dict:
    return post(
        client,
        "/api/batches/preview",
        {"path": str(path), "template": template, "account": account},
    )


def _submit(client, path: Path, template: str | None, account: str | None) -> dict:
    return post(
        client,
        "/api/batches",
        {"path": str(path), "template": template, "account": account},
    )


def run(args: object) -> int:
    ui = build(args)
    paths, settings, _ = load()
    source, template, draft = _choose_source(args, paths, settings, ui)
    if source is None:
        source, template, draft = _compose(paths, ui)
    body = _validate(source, template, settings, paths, ui)
    if not body["ok"]:
        if ui.json_mode:
            json_out(body)
        else:
            show_validation(body)
        return 1
    with api(paths, timeout=getattr(args, "timeout", None)) as client:
        account = _choose_account(client, args, ui)
        preview = _preview(client, source, template, account)
        if not ui.json_mode:
            show_preview(preview, ui)
        approval = _approval(args, ui)
        if approval == "all" and ui.interactive:
            print("warning: this sends without a second look")
        total = preview.get("total", 0)
        confirmed = getattr(args, "yes", False) or prompts.confirm(
            f"Submit {total:,} messages?",
            ui=ui,
            default=False,
        )
        if not confirmed:
            raise CliError("cancelled", code="cancelled")
        batch = _submit(client, source, template, account)
        if approval == "all":
            batch = post(client, f"/api/batches/{batch['id']}/approve", {"mode": "all"})
    if ui.json_mode:
        json_out({"preview": preview, "batch": batch})
        return 0
    record(
        {
            "submitted": f"{batch['id']} ({batch['name']})",
            "state": batch["state"],
            "approval": batch["approval"],
            "routing": "fixed, " + account if account else "auto",
            "draft": draft,
        }
    )
    show_capacity(batch.get("capacity"), ui)
    if not ui.quiet:
        if batch["state"] == "awaiting_approval":
            print(f"next: downcroc review, or downcroc batch approve {batch['id']}")
        else:
            print(f"next: downcroc batch show {batch['id']}")
    return 0
