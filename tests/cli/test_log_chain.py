from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tests.conftest import Stack

ROOT = Path(__file__).resolve().parents[2]


def _cli(stack: Stack, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "downcroc", *args],
        cwd=ROOT,
        env=stack.daemon.environment(),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_chain_renders_joined_boxes(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test"])
    result = _cli(stack, "logs", "--chain", "--glyphs", "nerd", "--limit", "3")
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert any(line.startswith("╭") for line in lines), result.stdout
    assert any(line.startswith("╰") for line in lines), result.stdout
    beads = [line for line in lines if line.strip() == "◆"]
    assert beads, result.stdout
    # Every bead sits at the midpoint of the surrounding box borders.
    top = next(line for line in lines if line.startswith("╭"))
    midpoint = len(top) // 2 - 1
    for bead in beads:
        assert bead.index("◆") == midpoint, repr(bead)
    # Boxes fill the terminal width (no hard 72-column cap).
    assert len(top) >= 80, len(top)


def test_chain_ascii_fallback(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test"])
    result = _cli(stack, "logs", "--chain", "--glyphs", "ascii", "--limit", "3")
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert any(line.startswith("+") for line in lines), result.stdout
    assert any(line.strip() == "*" for line in lines), result.stdout
    assert "╭" not in result.stdout


def test_chain_json_stays_canonical(stack_factory) -> None:
    """--json overrides --chain and keeps raw, line-per-event output."""
    stack = stack_factory(accounts=["alice@local.test"])
    result = _cli(stack, "logs", "--chain", "--json", "--limit", "1")
    assert result.returncode == 0, result.stderr
    entry = json.loads(result.stdout.strip())
    assert "event" in entry and "level" in entry
    assert "+" not in result.stdout[:2]
