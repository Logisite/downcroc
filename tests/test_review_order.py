from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

from tests.harness.campaigns import campaign_of, submit

ROOT = Path(__file__).resolve().parents[1]


def _cli(stack, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "downcroc", *args],
        cwd=ROOT,
        env=stack.daemon.environment(),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def _set_order(stack, value: str) -> None:
    config = stack.daemon.config / "config.toml"
    text = config.read_text(encoding="utf-8")
    text = text.replace('list_order = "oldest_first"', f'list_order = "{value}"')
    text = text.replace('list_order = "newest_first"', f'list_order = "{value}"')
    config.write_text(text, encoding="utf-8")


def test_review_honors_configured_list_order(stack_factory) -> None:
    stack = stack_factory(
        config_extra='\n[cli]\nlist_order = "oldest_first"\n',
        accounts=["alice@local.test"],
    )
    first = submit(
        stack, campaign_of(1, name="first", options={"approval": "review"}), "one.json"
    )
    second = submit(
        stack, campaign_of(1, name="second", options={"approval": "review"}), "two.json"
    )

    db = stack.daemon.data_home / "downcroc" / "downcroc.db"
    with closing(sqlite3.connect(db, timeout=10)) as connection:
        connection.execute(
            "UPDATE batches SET created_at = ? WHERE id = ?",
            ("2026-11-01T00:00:00.000Z", first["id"]),
        )
        connection.execute(
            "UPDATE batches SET created_at = ? WHERE id = ?",
            ("2026-11-02T00:00:00.000Z", second["id"]),
        )
        connection.commit()

    result = _cli(stack, "review", "--json")
    assert result.returncode == 0, result.stderr
    rows = json.loads(result.stdout)
    assert [row["name"] for row in rows] == ["first", "second"]

    _set_order(stack, "newest_first")
    result = _cli(stack, "review", "--json")
    assert result.returncode == 0, result.stderr
    rows = json.loads(result.stdout)
    assert [row["name"] for row in rows] == ["second", "first"]
