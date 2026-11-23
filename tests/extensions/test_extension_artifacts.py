from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tests.harness.logs import events

ROOT = Path(__file__).resolve().parents[2]

MANIFEST = """\
id = "artifact-demo"
name = "Artifact demo"
version = "1.0.0"
events = ["reply.attributed"]
capabilities = ["log"]
"""

MAIN = """\
import json
import sys
for line in sys.stdin:
    try:
        message = json.loads(line)
    except ValueError:
        continue
    if message.get("type") == "event":
        print(json.dumps({"actions": [{"capability": "log", "text": "artifact-ran"}]}), flush=True)
"""


def _cli(stack, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "downcroc", *args],
        cwd=ROOT,
        env={**stack.daemon.environment(), "NO_COLOR": "1"},
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def _source(tmp_path: Path) -> Path:
    source = tmp_path / "extension"
    source.mkdir()
    (source / "downcroc-extension.toml").write_text(MANIFEST, encoding="utf-8")
    (source / "__main__.py").write_text(MAIN, encoding="utf-8")
    return source


def _build(stack, tmp_path: Path) -> tuple[Path, str]:
    result = _cli(
        stack,
        "extension",
        "build",
        str(_source(tmp_path)),
        "--output",
        str(tmp_path / "artifact-demo.pyz"),
        "--json",
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    return Path(payload["path"]), str(payload["sha256"])


def test_build_install_and_run_artifact(stack_factory, tmp_path: Path) -> None:
    stack = stack_factory(accounts=[])
    artifact, checksum = _build(stack, tmp_path)
    assert artifact.is_file()

    added = _cli(stack, "extension", "add", str(artifact), "--json")
    assert added.returncode == 0, added.stderr
    payload = json.loads(added.stdout)
    assert payload["id"] == "artifact-demo"
    assert payload["sha256"] == checksum

    rows = stack.api.get("/api/extensions")
    row = next(item for item in rows if item["id"] == "artifact-demo")
    assert row["kind"] == "pyz"
    assert row["artifact_verified"] is True

    stack.api.post("/api/extensions/artifact-demo/enable")
    result = stack.api.post(
        "/api/extensions/artifact-demo/test",
        {"event": "reply.attributed", "message": "msg_1"},
    )
    assert result == [{"ok": True}]

    logged = events(stack).get("extension.call", [])
    assert any(item.get("capability") == "log" for item in logged)


def test_artifact_checksum_detects_corruption(stack_factory, tmp_path: Path) -> None:
    stack = stack_factory(accounts=[])
    artifact, _checksum = _build(stack, tmp_path)
    added = _cli(stack, "extension", "add", str(artifact), "--json")
    assert added.returncode == 0, added.stderr
    stack.api.post("/api/extensions/artifact-demo/enable")

    installed = (
        stack.daemon.config / "extensions" / "artifacts" / "artifact-demo-1.0.0.pyz"
    )
    installed.write_bytes(b"not a zipapp")

    verified = _cli(stack, "extension", "verify", "artifact-demo", "--json")
    assert verified.returncode == 0, verified.stderr
    assert json.loads(verified.stdout)["verified"] is False

    status, _body = stack.api.raw(
        "POST", "/api/extensions/artifact-demo/test", {"event": "reply.attributed"}
    )
    assert status == 500
    invalid = events(stack).get("extension.artifact_invalid", [])
    assert any(item.get("extension") == "artifact-demo" for item in invalid)
    assert not any(
        item.get("capability") == "log"
        for item in events(stack).get("extension.call", [])
    )
