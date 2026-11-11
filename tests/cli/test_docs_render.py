from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tests.conftest import Stack
from tests.harness.pty import Session

ROOT = Path(__file__).resolve().parents[2]


def _cli(stack: Stack, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "downcroc", *args],
        cwd=ROOT,
        env={**stack.daemon.environment(), "NO_COLOR": "1"},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_docs_list_search_and_render(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test"])

    listed = _cli(stack, "docs", "--list", "--json")
    assert listed.returncode == 0, listed.stderr
    pages = json.loads(listed.stdout)
    assert any(page["path"] == "concepts/smtp-seats.md" for page in pages)

    found = _cli(stack, "docs", "--search", "seat")
    assert found.returncode == 0, found.stderr
    assert "SMTP seats" in found.stdout

    rendered = _cli(stack, "docs", "smtp-seats", "--width", "60", "--no-pager")
    assert rendered.returncode == 0, rendered.stderr
    assert "SMTP seats" in rendered.stdout
    assert "downcroc doctor capacity" in rendered.stdout
    assert "# SMTP seats" not in rendered.stdout
    assert "\x1b[" not in rendered.stdout
    assert max(len(line) for line in rendered.stdout.splitlines()) <= 60


def test_docs_raw_matches_the_source(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test"])
    result = _cli(stack, "docs", "smtp-seats", "--raw")
    assert result.returncode == 0, result.stderr
    source = (ROOT / "docs" / "concepts" / "smtp-seats.md").read_text()
    assert result.stdout == source


def test_docs_missing_topic_is_a_usage_error(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test"])
    result = _cli(stack, "docs", "not-a-page")
    assert result.returncode == 2
    assert "docs_topic_not_found" in result.stderr


def test_docs_browser_opens_and_searches(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test"])
    session = Session(stack, "docs", width=120)
    try:
        session.wait_for(b"downcroc docs")
        session.write(b"/", 0.4)
        session.write(b"seat\r", 0.8)
        assert "SMTP seats" in "\n".join(session.screen())
    finally:
        session.write(b"\x03")
        session.close()
