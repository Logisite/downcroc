from __future__ import annotations

import json
import time
from pathlib import Path

from downcroc.core.inputs import campaign_input, csv_input, detector
from downcroc.core.inputs import templates as template_loader
from downcroc.core.inputs.limits import IntakeLimits
from downcroc.domain.campaign import Campaign
from downcroc.domain.errors import (
    BatchInvalid,
    DomainError,
    InputUnreadable,
)
from downcroc.runtime.config.schema import Settings
from downcroc.runtime.logging.setup import EventLogger
from downcroc.runtime.paths import Paths


class CampaignReader:
    def __init__(self, settings: Settings, paths: Paths, log: EventLogger) -> None:
        self._settings = settings
        self._paths = paths
        self._log = log

    def read(self, path: str, template: str | None) -> Campaign:
        try:
            return self._read_source(path, template)
        except DomainError as error:
            self._log_validation(error)
            raise

    def _read_source(self, path: str, template: str | None) -> Campaign:
        source = Path(path).expanduser()
        payload = detector.read_source(source, self._settings.intake.max_file_bytes)
        kind = detector.detect(payload)
        text = detector.decode(payload)
        limits = IntakeLimits(
            max_messages=self._settings.intake.max_messages,
            max_body_bytes=self._settings.intake.max_body_bytes,
            max_attachment_bytes=self._settings.intake.max_attachment_bytes,
        )
        if kind == "json":
            return self._read_json(text, source, template, limits)
        return self._read_csv(text, source, template, limits)

    def _read_json(
        self, text: str, source: Path, template: str | None, limits: IntakeLimits
    ) -> Campaign:
        if template:
            raise BatchInvalid(
                "a JSON campaign carries its own messages",
                fields={"template": "not allowed for JSON"},
            )
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as error:
            raise InputUnreadable(f"cannot parse JSON: {error}") from error
        return campaign_input.parse_campaign(
            raw,
            source_dir=source.parent,
            name=source.stem,
            limits=limits,
        )

    def _read_csv(
        self, text: str, source: Path, template: str | None, limits: IntakeLimits
    ) -> Campaign:
        if not template:
            raise BatchInvalid(
                "a CSV needs a template",
                fields={"template": "required for CSV"},
            )
        loaded = template_loader.load(self._paths.templates, template)
        started = time.monotonic()
        campaign = csv_input.parse_csv(
            text,
            template=loaded,
            source_name=str(source),
            limits=limits,
        )
        self._log.info(
            "template.rendered",
            name=template,
            duration_ms=round((time.monotonic() - started) * 1000, 2),
        )
        return campaign

    def _log_validation(self, error: DomainError) -> None:
        details = error.details or [
            {"code": error.code, "field": next(iter(error.fields or {}), "source")}
        ]
        first = details[0]
        self._log.info(
            "validation.failed",
            count=len(details),
            first_key=first.get("key"),
            first_field=first.get("field"),
        )
        for item in details:
            self._log.warning(
                "validation.row_rejected",
                key=item.get("key"),
                row=item.get("row"),
                field=item.get("field"),
                code=item.get("code"),
            )
