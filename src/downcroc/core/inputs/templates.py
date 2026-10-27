from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from downcroc.core.inputs.report import Issues
from downcroc.domain.errors import InputUnreadable

_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_VARIABLE = re.compile(r"\{\{\s*([A-Za-z0-9_.\- ]+?)\s*\}\}")


@dataclass(frozen=True)
class Template:
    name: str
    subject: str
    text: str
    html: str | None
    defaults: dict[str, str] = field(default_factory=dict)
    reply_to: str | None = None
    attachments: tuple[Path, ...] = ()


def resolve(root: Path, value: str) -> Path:
    looks_like_path = (
        "/" in value
        or "\\" in value
        or value.startswith("~")
        or Path(value).expanduser().is_dir()
    )
    if looks_like_path:
        return Path(value).expanduser().absolute()
    if not _NAME.match(value):
        raise InputUnreadable(f"invalid template name {value!r}")
    return root / value


def load(root: Path, name: str) -> Template:
    directory = resolve(root, name)
    name = directory.name
    if not _NAME.match(name):
        raise InputUnreadable(f"invalid template name {name!r}")
    manifest = directory / "template.toml"
    body_text = directory / "body.txt"
    if not manifest.is_file() or not body_text.is_file():
        raise InputUnreadable(
            f"template {name} is missing template.toml or body.txt",
            hint=f"create {directory} with template.toml and body.txt",
        )
    try:
        raw = tomllib.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise InputUnreadable(f"cannot read template {name}: {error}") from error
    subject = raw.get("subject")
    if not isinstance(subject, str) or not subject.strip():
        raise InputUnreadable(f"template {name} needs a non-empty subject")
    defaults = raw.get("defaults", {})
    if not isinstance(defaults, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in defaults.items()
    ):
        raise InputUnreadable(f"template {name} defaults must be a table of strings")
    reply_to = raw.get("reply_to")
    if reply_to is not None and not isinstance(reply_to, str):
        raise InputUnreadable(f"template {name} reply_to must be a string")

    html_path = directory / "body.html"
    html = html_path.read_text(encoding="utf-8") if html_path.is_file() else None
    text = body_text.read_text(encoding="utf-8")

    attachments: list[Path] = []
    declared = raw.get("attachments", [])
    if not isinstance(declared, list) or not all(
        isinstance(item, str) for item in declared
    ):
        raise InputUnreadable(
            f"template {name} attachments must be a list of filenames"
        )
    for item in declared:
        relative = Path(item)
        if relative.is_absolute() or ".." in relative.parts:
            raise InputUnreadable(
                f"template {name} attachment {item} escapes the template"
            )
        target = directory / "assets" / relative
        if not target.is_file():
            raise InputUnreadable(f"template {name} attachment {item} does not exist")
        attachments.append(target)

    return Template(
        name=name,
        subject=subject,
        text=text,
        html=html,
        defaults=dict(defaults),
        reply_to=reply_to,
        attachments=tuple(attachments),
    )


def variables_in(text: str) -> list[str]:
    return [match.group(1) for match in _VARIABLE.finditer(text)]


def render(
    text: str,
    values: dict[str, str],
    defaults: dict[str, str],
    *,
    field_name: str,
    issues: Issues,
    row: int | None = None,
    key: str | None = None,
) -> str:
    folded_values = {name.strip().casefold(): value for name, value in values.items()}
    folded_defaults = {
        name.strip().casefold(): value for name, value in defaults.items()
    }

    def replace(match: re.Match[str]) -> str:
        name = match.group(1).strip()
        folded = name.casefold()
        if folded in folded_values:
            return folded_values[folded]
        if folded in folded_defaults:
            return folded_defaults[folded]
        issues.add(
            "missing_variable",
            f"missing value for {name}",
            field_name,
            key=key,
            row=row,
        )
        return ""

    return _VARIABLE.sub(replace, text)
