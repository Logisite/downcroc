from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tests.conftest import Stack
from tests.harness.campaigns import campaign_of, input_files, submit
from tests.harness.logs import events
from tests.harness.pty import Session
from tests.harness.seed import write_json

ROOT = Path(__file__).resolve().parents[2]


def _cli(stack: Stack, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "downcroc", *args],
        cwd=ROOT,
        env=stack.daemon.environment(),
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


def _json(result: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(result.stdout)


def test_editor_shows_cursor_and_completes_a_path(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test"])

    session = Session(stack, "account", "add", width=80)
    try:
        session.wait_for(b"enter select")
        session.write(b"\r", 0.6)
        session.wait_for(b"Mailbox address")
        chunk = session.write(b"abc", 0.6)
        assert b"\x1b[?25h" in chunk
        assert "abc" in "\n".join(session.screen())
    finally:
        session.write(b"\x03")
        session.close()

    directory = stack.root / "clients"
    directory.mkdir()
    (directory / "client.json").write_text("{}", encoding="utf-8")
    session = Session(stack, "provider", "credentials", "set", "gmail", width=100)
    try:
        session.wait_for(b"Client JSON path")
        session.write(str(directory / "clie").encode(), 0.6)
        session.write(b"\t", 0.8)
        assert "client.json" in "\n".join(session.screen())
    finally:
        session.write(b"\x03")
        session.close()


def test_batch_overlap_warns_before_writing(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test"])
    first = submit(stack, campaign_of(1), name="first.json")
    path = write_json(
        input_files(stack),
        "second.json",
        campaign_of(1, key="second"),
    )

    result = _cli(stack, "batch", "validate", str(path), "--json")
    assert result.returncode == 0, result.stderr
    body = _json(result)
    assert body["overlap"]["count"] == 1
    assert body["overlap"]["batches"] == [first["id"]]

    result = _cli(stack, "batch", "submit", str(path), "--dry-run", "--json")
    assert result.returncode == 0, result.stderr
    preview = _json(result)["preview"]
    assert preview["overlap"]["count"] == 1

    result = _cli(stack, "batch", "submit", str(path), "--json")
    assert result.returncode == 1
    assert "confirmation_required" in result.stderr

    result = _cli(
        stack,
        "batch",
        "submit",
        str(path),
        "--allow-overlap",
        "--json",
    )
    assert result.returncode == 0, result.stderr
    assert _json(result)["id"] != first["id"]

    warning = events(stack)["batch.duplicate_warning"][-1]
    assert warning["count"] >= 1
    assert first["id"] in warning["batches"]
    assert "person1@example.com" not in json.dumps(warning)


def test_same_file_and_key_still_reuses_the_batch(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test"])
    path = write_json(input_files(stack), "reuse.json", campaign_of(1))

    first = _cli(
        stack,
        "batch",
        "submit",
        str(path),
        "--key",
        "m1",
        "--allow-overlap",
        "--json",
    )
    assert first.returncode == 0, first.stderr
    second = _cli(
        stack,
        "batch",
        "submit",
        str(path),
        "--key",
        "m1",
        "--allow-overlap",
        "--json",
    )
    assert second.returncode == 0, second.stderr
    assert _json(second)["reused"] is True
