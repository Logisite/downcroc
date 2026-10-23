from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from pathlib import Path

from downcroc.core.inputs.limits import IntakeLimits
from downcroc.core.inputs.report import Issues
from downcroc.core.inputs.templates import Template, render
from downcroc.domain.campaign import (
    SCHEMA,
    Campaign,
    CampaignOptions,
    Message,
    Recipient,
    RoutingPolicy,
)
from downcroc.domain.errors import BatchInvalid
from downcroc.domain.validators import ADDRESS

_MAX_SUBJECT = 998


def parse_csv(
    text: str,
    *,
    template: Template,
    source_name: str,
    limits: IntakeLimits,
) -> Campaign:
    issues = Issues()
    rows = _rows(text, issues)
    if not rows:
        raise BatchInvalid("the CSV has no header row")
    header = [_clean(cell) for cell in rows[0]]
    if not header or not any(header):
        raise BatchInvalid("the CSV header is empty")
    folded = [name.casefold() for name in header]
    if len(set(folded)) != len(folded):
        duplicates = sorted(
            {name for name in header if folded.count(name.casefold()) > 1}
        )
        raise BatchInvalid(
            "duplicate CSV headers are ambiguous",
            fields={"header": f"duplicate headers: {', '.join(duplicates)}"},
        )
    if "email" not in folded:
        raise BatchInvalid(
            "the CSV needs an email column",
            fields={"header": "missing email column"},
        )
    data = [row for row in rows[1:] if any(_clean(cell) for cell in row)]
    if len(data) > limits.max_messages:
        raise BatchInvalid(
            f"{len(data)} rows exceeds the limit of {limits.max_messages}",
            hint="split the file or raise intake.max_messages",
        )
    if not data:
        raise BatchInvalid("the CSV has no data rows")

    messages: list[Message] = []
    seen: set[str] = set()
    duplicates = 0
    for offset, row in enumerate(data):
        line = offset + 2
        if len(row) != len(header):
            issues.add(
                "row_shape",
                f"row {line} has {len(row)} cells, expected {len(header)}",
                "row",
                row=line,
            )
            continue
        values = {name: _clean(cell) for name, cell in zip(header, row, strict=True)}
        email = values.get(_column(header, "email"), "")
        if not ADDRESS.fullmatch(email):
            issues.add(
                "invalid_address",
                f"row {line} email {email!r} is not an address",
                "email",
                row=line,
            )
            continue
        address = email.casefold()
        if address in seen:
            duplicates += 1
            continue
        seen.add(address)

        variables = _variables(values, email, template.name)
        subject = render(
            template.subject,
            variables,
            template.defaults,
            field_name="subject",
            issues=issues,
            row=line,
        )
        body = render(
            template.text,
            variables,
            template.defaults,
            field_name="text",
            issues=issues,
            row=line,
        )
        html = (
            render(
                template.html,
                variables,
                template.defaults,
                field_name="html",
                issues=issues,
                row=line,
            )
            if template.html
            else None
        )
        messages.append(
            Message(
                key=f"r{line}",
                recipient=Recipient(
                    email=email, name=values.get(_column(header, "name")) or None
                ),
                subject=subject,
                text=body,
                html=html,
                reply_to=template.reply_to,
                attachments=tuple(str(path) for path in template.attachments),
                source_index=line,
            )
        )

    issues.raise_if_any()
    name = Path(source_name).stem
    return Campaign(
        schema=SCHEMA,
        key=name,
        name=name,
        producer={},
        routing=RoutingPolicy(),
        options=CampaignOptions(),
        messages=tuple(messages),
        followups=(),
        source_kind="csv",
        source_dir=str(Path(source_name).parent),
        template=template.name,
        duplicates=duplicates,
    )


def _rows(text: str, issues: Issues) -> list[list[str]]:
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    try:
        return list(csv.reader(io.StringIO(text), dialect))
    except csv.Error as error:
        issues.add("csv_parse", f"cannot parse the CSV: {error}", "csv")
        return []


def _variables(
    values: dict[str, str], email: str, template_name: str
) -> dict[str, str]:
    variables = dict(values)
    variables["email"] = email
    variables["batch_name"] = template_name
    variables["date"] = datetime.now(UTC).date().isoformat()
    return variables


def _column(header: list[str], wanted: str) -> str:
    for name in header:
        if name.casefold() == wanted:
            return name
    return wanted


def _clean(value: str) -> str:
    return value.strip()
