from __future__ import annotations

from pathlib import Path

from downcroc.cli.context import load
from downcroc.cli.errors import CliError
from downcroc.cli.output import json_out, record, table
from downcroc.cli.ui.menu import open_menu
from downcroc.cli.ui.session import Ui, build
from downcroc.core.inputs import templates as template_files
from downcroc.core.inputs.templates import Template
from downcroc.domain.errors import InputUnreadable

MANIFEST = 'subject = "Hello {{ name }}"\nreply_to = "you@example.com"\n\n[defaults]\nname = "there"\n'

BODY = (
    "Hi {{ name }},\n\n"
    "this is a plain text template. Variables are {{ name }} and {{ company }}.\n"
)


def _directories(paths: object) -> list[Path]:
    root: Path = paths.templates
    if not root.is_dir():
        return []
    return sorted(
        child
        for child in root.iterdir()
        if child.is_dir() and (child / "template.toml").is_file()
    )


def _list(paths: object, ui: Ui) -> int:
    rows = []
    broken = []
    for directory in _directories(paths):
        try:
            template = template_files.load(paths.templates, directory.name)
        except InputUnreadable as error:
            broken.append({"name": directory.name, "error": str(error)})
            continue
        variables = sorted(
            set(
                template_files.variables_in(template.subject)
                + template_files.variables_in(template.text)
                + template_files.variables_in(template.html or "")
            )
        )
        rows.append(
            {
                "name": template.name,
                "subject": template.subject,
                "variables": variables,
                "defaults": sorted(template.defaults),
                "attachments": len(template.attachments),
                "path": str(directory),
            }
        )
    if ui.json_mode:
        json_out({"templates": rows, "broken": broken})
        return 0 if not broken else 1
    if not rows and not broken:
        print("no templates yet")
        if not ui.quiet:
            print("next: downcroc template new intro")
        return 0
    table(
        ["name", "subject", "variables", "defaults", "files"],
        [
            [
                row["name"],
                row["subject"],
                ", ".join(row["variables"]) or "none",
                ", ".join(row["defaults"]) or "none",
                row["attachments"],
            ]
            for row in rows
        ],
    )
    for item in broken:
        print(ui.result(False, f"{item['name']}: {item['error']}"))
    if not ui.quiet:
        print()
        print(f"templates: {paths.templates}")
    return 0 if not broken else 1


def _new(args: object, paths: object, ui: Ui) -> int:
    name = str(args.name)
    target = template_files.resolve(paths.templates, name)
    if target.exists():
        raise CliError(
            "the template already exists",
            code="template_exists",
            fields={"path": str(target)},
            hint="pick another name, or edit the existing files",
        )
    target.mkdir(parents=True)
    manifest = target / "template.toml"
    body = target / "body.txt"
    manifest.write_text(MANIFEST, encoding="utf-8")
    body.write_text(BODY, encoding="utf-8")
    if ui.json_mode:
        json_out({"name": target.name, "path": str(target)})
        return 0
    record(
        {
            "template": target.name,
            "path": str(target),
            "manifest": str(manifest),
            "body": str(body),
        }
    )
    if not ui.quiet:
        print(f"next: edit {manifest}, then downcroc template validate {target.name}")
    return 0


def _show(args: object, paths: object, ui: Ui) -> int:
    template = _load(args, paths)
    if ui.json_mode:
        json_out(
            {
                "name": template.name,
                "subject": template.subject,
                "text": template.text,
                "html": template.html,
                "defaults": template.defaults,
                "reply_to": template.reply_to,
                "attachments": [str(item) for item in template.attachments],
            }
        )
        return 0
    record(
        {
            "name": template.name,
            "subject": template.subject,
            "reply_to": template.reply_to,
            "defaults": template.defaults,
        }
    )
    print()
    print(template.text.rstrip())
    if template.html:
        print()
        print(f"html: {len(template.html)} characters")
    for item in template.attachments:
        print(f"attachment: {item}")
    return 0


def _validate(args: object, paths: object, ui: Ui) -> int:
    try:
        template = _load(args, paths)
    except CliError as error:
        if ui.json_mode:
            json_out({"ok": False, "error": error.as_json()})
        else:
            print(ui.result(False, error.message))
            if error.hint:
                print(f"  hint: {error.hint}")
        return 1
    variables = sorted(
        set(
            template_files.variables_in(template.subject)
            + template_files.variables_in(template.text)
            + template_files.variables_in(template.html or "")
        )
    )
    missing = [
        name for name in variables if name.casefold() not in _folded_defaults(template)
    ]
    if ui.json_mode:
        json_out(
            {
                "ok": True,
                "name": template.name,
                "variables": variables,
                "defaults": sorted(template.defaults),
                "needs_columns": missing,
                "attachments": [str(item) for item in template.attachments],
            }
        )
        return 0
    record(
        {
            "template": template.name,
            "subject": template.subject,
            "variables": ", ".join(variables) or "none",
            "defaults": ", ".join(sorted(template.defaults)) or "none",
            "csv columns": ", ".join(["email", *missing]),
            "attachments": len(template.attachments),
        }
    )
    print(ui.result(True, "template is valid"))
    return 0


def _folded_defaults(template: Template) -> set[str]:
    return {name.casefold() for name in template.defaults}


def _load(args: object, paths: object) -> Template:
    try:
        return template_files.load(paths.templates, str(args.name))
    except InputUnreadable as error:
        raise CliError(
            str(error),
            code="template_invalid",
            hint=getattr(error, "hint", None),
            fields={"template": str(args.name)},
        ) from error


def run(args: object) -> int:
    ui = build(args)
    paths, _, _ = load()
    action = getattr(args, "action", None)
    if action is None:
        if open_menu(ui, "template_menu"):
            return 0
        action = "list"
    if action == "list":
        return _list(paths, ui)
    if action == "new":
        return _new(args, paths, ui)
    if action == "show":
        return _show(args, paths, ui)
    return _validate(args, paths, ui)
