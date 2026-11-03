from __future__ import annotations

from downcroc.cli import paths as path_tools
from downcroc.cli.client import api, delete, get, put
from downcroc.cli.commands import provider_credentials
from downcroc.cli.context import load
from downcroc.cli.errors import CliError, no_terminal
from downcroc.cli.output import json_out, record, table
from downcroc.cli.ui import prompts
from downcroc.cli.ui.menu import count_label
from downcroc.cli.ui.session import Ui, build


def _host(value: str, port: int) -> str:
    if not value:
        return "not set"
    return f"{value}:{port}" if port else value


def _missing(provider: dict) -> str:
    if provider["ready"]:
        return ""
    return "set " + " and ".join(provider["missing"])


def show_list(rows: list[dict], ui: Ui) -> None:
    table(
        ["provider", "label", "door", "imap", "smtp", "ready", "note"],
        [
            [
                item["id"],
                item["label"],
                item["auth_kind"],
                _host(item["imap_host"], item["imap_port"]),
                _host(item["smtp_host"], item["smtp_port"]),
                "yes" if item["ready"] else "no",
                _missing(item) or item["notes"],
            ]
            for item in rows
        ],
    )
    notes = [item for item in rows if item["notes"] and item["ready"]]
    if notes:
        print()
        for item in notes:
            print(f"{item['id']}: {item['notes']}")
    if not ui.quiet:
        print()
        print("next: downcroc provider show gmail")


def _show(provider: dict, ui: Ui) -> None:
    record(
        {
            "id": provider["id"],
            "label": provider["label"],
            "door": provider["auth_kind"],
            "ready": provider["ready"],
            "source": provider["source"] or "built in",
        }
    )
    record(
        {
            "imap": _host(provider["imap_host"], provider["imap_port"]),
            "imap_tls": provider["imap_tls"],
            "smtp": _host(provider["smtp_host"], provider["smtp_port"]),
            "smtp_tls": provider["smtp_tls"],
            "sent_folder": provider["sent_folder"],
            "attachment_max_bytes": provider["attachment_max_bytes"],
            "transport": provider["transport"],
        }
    )
    if provider["transport"] == "gmail_api":
        record(
            {
                "api_base_url": provider["api_base_url"],
                "api_max_concurrency": provider["api_max_concurrency"],
                "api_rate_per_min": provider["api_rate_per_min"],
            }
        )
    if provider["missing"]:
        record({"missing": ", ".join(provider["missing"])})
    if provider["notes"]:
        print()
        print(provider["notes"])
    if not ui.quiet:
        print()
        print(f"next: downcroc provider edit {provider['id']}")


def _flag_values(args: object) -> dict:
    return {
        "label": getattr(args, "label", None),
        "imap_host": getattr(args, "imap_host", None),
        "imap_port": getattr(args, "imap_port", None),
        "imap_tls": getattr(args, "imap_tls", None),
        "smtp_host": getattr(args, "smtp_host", None),
        "smtp_port": getattr(args, "smtp_port", None),
        "smtp_tls": getattr(args, "smtp_tls", None),
        "auth_kind": getattr(args, "auth_kind", None),
        "sent_folder": getattr(args, "sent_folder", None),
        "notes": getattr(args, "notes", None),
        "oauth_client_id": getattr(args, "oauth_client_id", None),
        "oauth_tenant": getattr(args, "oauth_tenant", None),
        "transport": getattr(args, "transport", None),
        "api_base_url": getattr(args, "api_base_url", None),
        "api_max_concurrency": getattr(args, "api_max_concurrency", None),
        "api_rate_per_min": getattr(args, "api_rate_per_min", None),
    }


def _secret(args: object, ui: Ui) -> str | None:
    path = getattr(args, "password_file", None)
    if path:
        return path_tools.read_secret(path)
    if not ui.interactive or getattr(args, "auth_kind", None) != "oauth2":
        return None
    return prompts.ask_secret("OAuth client secret", ui=ui)


def _prompt_values(ui: Ui, provider_id: str) -> dict:
    values: dict = {
        "label": prompts.ask("Label", ui=ui, default=provider_id, required=False),
        "imap_host": prompts.ask("IMAP host", ui=ui, field="--imap-host"),
        "imap_port": prompts.ask("IMAP port", ui=ui, default="993"),
        "imap_tls": _tls(ui, "IMAP encryption", ("ssl", "starttls", "none")),
        "smtp_host": prompts.ask("SMTP host", ui=ui, field="--smtp-host"),
        "smtp_port": prompts.ask("SMTP port", ui=ui, default="587"),
        "smtp_tls": _tls(ui, "SMTP encryption", ("starttls", "ssl", "none")),
        "auth_kind": _auth(ui),
        "sent_folder": prompts.ask(
            "Sent folder", ui=ui, default="Sent", required=False
        ),
    }
    if values.get("auth_kind") == "oauth2":
        values["oauth_client_id"] = prompts.ask("OAuth client id", ui=ui, required=True)
        if "microsoft" in provider_id.casefold():
            values["oauth_tenant"] = prompts.ask(
                "OAuth tenant", ui=ui, default="common"
            )
        secret = prompts.ask_secret(
            "OAuth client secret", ui=ui, required=False, flag="--password-file"
        )
        if secret:
            values["oauth_client_secret"] = secret
    return {key: value for key, value in values.items() if value not in ("", None)}


def _tls(ui: Ui, title: str, choices: tuple[str, ...]) -> str:
    return str(
        prompts.choose(
            title,
            [prompts.Option(name, name) for name in choices],
            ui=ui,
            default=0,
            back=False,
        )
    )


def _auth(ui: Ui) -> str:
    return str(
        prompts.choose(
            "Authentication",
            [
                prompts.Option("app password", "app_password", "about 2 minutes"),
                prompts.Option("oauth client", "oauth2", "browser sign-in"),
            ],
            ui=ui,
            default=0,
            back=False,
        )
    )


def _write(args: object, client, ui: Ui, values: dict) -> dict:
    return put(client, f"/api/providers/{args.provider_id}", values)


def _add(args: object, ui: Ui) -> int:
    paths, _, _ = load()
    if not getattr(args, "provider_id", None):
        args.provider_id = prompts.ask("Provider id", ui=ui, field="PROVIDER")
    values = _flag_values(args)
    secret = _secret(args, ui)
    if secret:
        values["oauth_client_secret"] = secret
    if not any(value for value in values.values()):
        if not ui.interactive:
            raise no_terminal("--imap-host")
        values = _prompt_values(ui, args.provider_id)
    values = {key: value for key, value in values.items() if value is not None}
    with api(paths) as client:
        provider = _write(args, client, ui, values)
    if ui.json_mode:
        json_out(provider)
        return 0
    record({"provider": provider["id"], "ready": provider["ready"]})
    if provider["missing"]:
        print(f"missing    {', '.join(provider['missing'])}")
        print(f"next: downcroc provider edit {provider['id']}")
    return 0


def _edit(args: object, ui: Ui) -> int:
    paths, _, _ = load()
    values = _flag_values(args)
    secret = _secret(args, ui)
    if secret:
        values["oauth_client_secret"] = secret
    values = {key: value for key, value in values.items() if value is not None}
    if not values:
        if not ui.interactive:
            raise no_terminal("--imap-host")
        return _edit_fields(args, paths, ui)
    with api(paths) as client:
        provider = _write(args, client, ui, values)
    if ui.json_mode:
        json_out(provider)
    else:
        record({"provider": provider["id"], "ready": provider["ready"]})
        if not ui.quiet:
            print(f"wrote {provider['source'] or paths.config / 'providers.toml'}")
    return 0


def _remove(args: object, ui: Ui) -> int:
    paths, _, _ = load()
    confirmed = getattr(args, "yes", False) or prompts.confirm(
        f"Remove the {args.provider_id} provider?",
        ui=ui,
        default=False,
    )
    if not confirmed:
        raise CliError("cancelled", code="cancelled")
    with api(paths) as client:
        delete(client, f"/api/providers/{args.provider_id}")
    if ui.json_mode:
        json_out({"removed": args.provider_id})
    else:
        record({"provider": f"{args.provider_id} removed"})
    return 0


def _edit_fields(args: object, paths, ui: Ui) -> int:
    with api(paths) as client:
        provider = get(client, f"/api/providers/{args.provider_id}")
    fields = [
        ("label", "Label", provider.get("label")),
        ("imap_host", "IMAP host", provider.get("imap_host")),
        ("imap_port", "IMAP port", provider.get("imap_port")),
        ("imap_tls", "IMAP encryption", provider.get("imap_tls")),
        ("smtp_host", "SMTP host", provider.get("smtp_host")),
        ("smtp_port", "SMTP port", provider.get("smtp_port")),
        ("smtp_tls", "SMTP encryption", provider.get("smtp_tls")),
        ("auth_kind", "Authentication", provider.get("auth_kind")),
        ("sent_folder", "Sent folder", provider.get("sent_folder")),
    ]
    chosen = prompts.choose_many(
        "Fields to change",
        [
            prompts.Option(label, key, "" if value is None else str(value))
            for key, label, value in fields
        ],
        ui=ui,
    )
    if not chosen:
        print(ui.dim("nothing changed"))
        return 0
    current = {key: value for key, _label, value in fields}
    values: dict = {}
    for key in chosen:
        values[key] = _edit_value(ui, key, current.get(key))
    values = {key: value for key, value in values.items() if value is not None}
    with api(paths) as client:
        updated = _write(args, client, ui, values)
    if ui.json_mode:
        json_out(updated)
        return 0
    record({"provider": updated["id"], "ready": updated["ready"]})
    if updated["missing"]:
        print(f"missing    {', '.join(updated['missing'])}")
    return 0


def _edit_value(ui: Ui, key: str, current: object) -> object:
    if key == "imap_tls":
        return _pick(ui, "IMAP encryption", ("ssl", "starttls", "none"), current)
    if key == "smtp_tls":
        return _pick(ui, "SMTP encryption", ("starttls", "ssl", "none"), current)
    if key == "auth_kind":
        return _pick(ui, "Authentication", ("app_password", "oauth2", "none"), current)
    if key == "imap_port":
        return prompts.ask("IMAP port", ui=ui, default=str(current or 993))
    if key == "smtp_port":
        return prompts.ask("SMTP port", ui=ui, default=str(current or 587))
    return prompts.ask(
        key.replace("_", " ").capitalize(),
        ui=ui,
        default="" if current is None else str(current),
        required=False,
    )


def _pick(ui: Ui, title: str, choices: tuple[str, ...], current: object) -> str:
    default = choices.index(str(current)) if str(current) in choices else 0
    return str(
        prompts.choose(
            title,
            [prompts.Option(name, name) for name in choices],
            ui=ui,
            default=default,
            back=False,
        )
    )


def run(args: object) -> int:
    ui = build(args)
    paths, _, _ = load()
    action = args.action
    if action == "credentials":
        return provider_credentials.run(args, ui)
    if action is None and ui.interactive:
        from downcroc.cli.ui.tree import open_path

        open_path(ui, ("provider",))
        return 0
    if action in {"show", "edit", "remove"} and not getattr(args, "provider_id", None):
        if not ui.interactive:
            raise CliError(f"{action} needs a provider id", code="usage", exit_code=2)
        with api(paths) as client:
            args.provider_id = provider_credentials.choose_provider(
                client, ui, f"Provider to {action}"
            )
    if action == "add":
        return _add(args, ui)
    if action == "edit":
        return _edit(args, ui)
    if action == "remove":
        return _remove(args, ui)
    with api(paths) as client:
        if action == "show":
            provider = get(client, f"/api/providers/{args.provider_id}")
            if ui.json_mode:
                json_out(provider)
            else:
                _show(provider, ui)
            return 0
        rows = get(client, "/api/providers")
    if ui.json_mode:
        json_out(rows)
        return 0
    show_list(rows, ui)
    return 0


def conclusion(rows: list[dict]) -> str:
    ready = sum(1 for row in rows if row["ready"])
    return f"{count_label(ready, 'provider')} ready of {len(rows)}"
