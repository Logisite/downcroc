from __future__ import annotations

import json
import time
from pathlib import Path

from tests.conftest import Stack
from tests.harness.inbound import cli


def _cache(stack: Stack, *, latest: str, current: str = "1.3.3.post1") -> Path:
    path = stack.daemon.state_home / "downcroc" / "update-check.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "checked_at": time.time(),
                "current": current,
                "latest": latest,
                "url": "https://github.com/Logisite/downcroc/releases",
            }
        ),
        encoding="utf-8",
    )
    return path


def test_footer_shown_when_update_available(stack_factory) -> None:
    stack = stack_factory(accounts=[])
    _cache(stack, latest="99.0.0")
    result = cli(stack, "help")
    assert result.returncode == 0
    assert "Update available" in result.stdout
    assert "99.0.0 available" in result.stdout
    assert "downcroc update" in result.stdout


def test_no_footer_when_up_to_date(stack_factory) -> None:
    stack = stack_factory(accounts=[])
    _cache(stack, latest="1.3.3.post1", current="1.3.3.post1")
    result = cli(stack, "help")
    assert result.returncode == 0
    assert "Update available" not in result.stdout


def test_footer_suppressed_by_quiet(stack_factory) -> None:
    stack = stack_factory(accounts=[])
    _cache(stack, latest="99.0.0")
    result = cli(stack, "help", "--quiet")
    assert result.returncode == 0
    assert "Update available" not in result.stdout


def test_footer_suppressed_by_json(stack_factory) -> None:
    stack = stack_factory(accounts=[])
    _cache(stack, latest="99.0.0")
    result = cli(stack, "batch", "validate", "--help", "--json")
    assert result.returncode == 0
    assert "Update available" not in result.stdout


def test_footer_suppressed_by_config(stack_factory) -> None:
    stack = stack_factory(accounts=[], config_extra="\n[cli]\nupdate_check = false\n")
    _cache(stack, latest="99.0.0")
    result = cli(stack, "help")
    assert result.returncode == 0
    assert "Update available" not in result.stdout


def test_version_never_shows_footer(stack_factory) -> None:
    stack = stack_factory(accounts=[])
    _cache(stack, latest="99.0.0")
    result = cli(stack, "--version")
    assert result.returncode == 0
    assert "Update available" not in result.stdout
