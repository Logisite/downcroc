from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from downcroc.runtime.config.schema import Settings
from tests.conftest import Stack
from tests.harness.campaigns import campaign_of, submit
from tests.harness.dispatch import dispatch_config
from tests.harness.logs import events
from tests.harness.seed import until

ROOT = Path(__file__).resolve().parents[1]


def _config_path(stack: Stack) -> Path:
    return stack.daemon.config / "config.toml"


def _cli(stack: Stack, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "downcroc", *args],
        cwd=ROOT,
        env=stack.daemon.environment(),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_schema_lists_every_field(stack: Stack) -> None:
    schema = stack.api.get("/api/config/schema")
    fields = {field["path"]: field for field in schema["fields"]}
    defaults = Settings()
    expected = {
        f"{section}.{name}"
        for section in Settings.model_fields
        for name in type(getattr(defaults, section)).model_fields
    }
    assert set(fields) == expected
    for field in fields.values():
        assert field["description"]
        assert field["type"] != "unknown"
        assert "default" in field
    jitter = fields["sending.jitter_min"]
    assert jitter["type"] == "integer"
    assert jitter["default"] == 30
    assert jitter["range"] == {"minimum": 0, "maximum": 3600}
    level = fields["logging.level"]
    assert level["type"] == "string"
    assert level["values"] == ["debug", "info", "warning", "error"]
    backoff = fields["inbound.backoff_s"]
    assert backoff["type"] == "array"
    assert backoff["range"]["minItems"] == 1
    assert backoff["range"]["maxItems"] == 16
    port = fields["daemon.port"]
    assert port["restart_required"] is True


def test_patching_jitter_applies_to_the_next_send(stack_factory) -> None:
    stack = stack_factory(
        config_extra=dispatch_config(
            jitter_min=0,
            jitter_max=0,
            max_in_flight=1,
        ),
        accounts=["alice@local.test"],
    )
    account_id = stack.accounts[0]
    assert stack.api.get(f"/api/accounts/{account_id}")["quota"]["jitter_min"] == 0

    result = stack.api.patch(
        "/api/config",
        {"sending": {"jitter_min": 2, "jitter_max": 2}},
    )

    assert result["changed"] == ["sending.jitter_max", "sending.jitter_min"]
    assert result["config"]["sending"]["jitter_min"] == 2
    quota = stack.api.get(f"/api/accounts/{account_id}")["quota"]
    assert quota["jitter_min"] == 2
    assert quota["jitter_max"] == 2

    submit(stack, campaign_of(2, options={"approval": "auto"}))
    until(lambda: len(stack.fakes.sent()) >= 1)
    started = time.monotonic()
    until(lambda: len(stack.fakes.sent()) >= 2, timeout=15.0)
    elapsed = time.monotonic() - started
    assert elapsed >= 1.5


def test_out_of_range_patch_is_rejected_and_file_unchanged(stack: Stack) -> None:
    path = _config_path(stack)
    before = path.read_bytes()

    status, body = stack.api.raw(
        "PATCH",
        "/api/config",
        {"sending": {"jitter_min": 99_999}},
    )

    assert status == 422
    assert body["error"] == "config_rejected"
    assert body["fields"]["field"] == "sending.jitter_min"
    assert "3600" in body["fields"]["reason"]
    assert path.read_bytes() == before
    assert stack.api.get("/api/config")["config"]["sending"]["jitter_min"] == 30
    rejected = events(stack)["config.rejected"][-1]
    assert rejected["field"] == "sending.jitter_min"
    assert "3600" in rejected["reason"]


def test_hand_edited_config_reloads(stack_factory) -> None:
    stack = stack_factory(
        config_extra=dispatch_config(jitter_min=0, jitter_max=0),
        accounts=["alice@local.test"],
    )
    path = _config_path(stack)
    text = path.read_text()
    assert "jitter_min = 0" in text

    path.write_text(
        text.replace("jitter_min = 0", "jitter_min = 4").replace(
            "jitter_max = 0",
            "jitter_max = 4",
        )
    )

    until(lambda: stack.api.get("/api/config")["config"]["sending"]["jitter_min"] == 4)
    quota = stack.api.get(f"/api/accounts/{stack.accounts[0]}")["quota"]
    assert quota["jitter_min"] == 4
    assert quota["jitter_max"] == 4
    reloaded = events(stack)["config.reloaded"][-1]
    assert "sending.jitter_min" in reloaded["changed"]


def test_malformed_config_is_reported_and_previous_values_stay(
    stack_factory,
) -> None:
    stack = stack_factory(
        config_extra=dispatch_config(jitter_min=0, jitter_max=0),
        accounts=["alice@local.test"],
    )
    path = _config_path(stack)
    text = path.read_text()
    before = stack.api.get("/api/config")["config"]

    path.write_text("[sending\n")

    until(lambda: "config.rejected" in events(stack))
    rejected = events(stack)["config.rejected"][-1]
    assert rejected["field"] == "config.toml"
    assert "invalid TOML" in rejected["reason"]
    assert stack.api.get("/api/config")["config"] == before
    assert stack.api.get("/api/health")["status"] == "ok"

    path.write_text(
        text.replace("jitter_min = 0", "jitter_min = 5").replace(
            "jitter_max = 0",
            "jitter_max = 5",
        )
    )
    until(lambda: stack.api.get("/api/config")["config"]["sending"]["jitter_min"] == 5)
    assert (
        stack.api.get(f"/api/accounts/{stack.accounts[0]}")["quota"]["jitter_min"] == 5
    )


def test_openapi_export_covers_the_api(stack: Stack) -> None:
    output = stack.root / "openapi.json"

    result = _cli(stack, "openapi", "-o", str(output))

    assert result.returncode == 0, result.stderr
    exported = json.loads(output.read_text())
    assert exported["openapi"]
    assert "/api/health" in exported["paths"]
    assert "/api/service/stop" in exported["paths"]
    assert "/openapi.json" not in exported["paths"]
    exported_event = events(stack)["openapi.exported"][-1]
    assert exported_event["path"] == str(output)
    assert exported_event["routes"] > 0
