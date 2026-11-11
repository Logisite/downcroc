from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tests.conftest import Stack
from tests.harness.campaigns import campaign_of, input_files, submit
from tests.harness.followups import done
from tests.harness.seed import write_json

ROOT = Path(__file__).resolve().parents[2]


def patch(after_days: int = 1, **extra) -> dict:
    document = {
        "after_days": after_days,
        "when": "no_reply",
        "subject": "",
        "text": "Just following up.",
        "require_approval": False,
    }
    document.update(extra)
    return document


def payload(followup: dict, messages: list[dict]) -> dict:
    return {"followup": followup, "messages": messages}


def parent(stack: Stack, count: int = 1, name: str = "parent.json") -> dict:
    batch = submit(stack, campaign_of(count, options={"approval": "auto"}), name)
    done(stack, batch["id"])
    return batch


def declare(
    stack: Stack,
    parent: str,
    step_key: str,
    document: object,
    name: str,
    **extra,
) -> tuple[int, dict]:
    path = write_json(input_files(stack), name, document)
    return stack.api.raw(
        "PUT",
        f"/api/batches/{parent}/followups/{step_key}",
        {"path": str(path), **extra},
    )


def declare_ok(
    stack: Stack, parent: str, step_key: str, document, name, **extra
) -> dict:
    status, report = declare(stack, parent, step_key, document, name, **extra)
    assert status == 200, report
    return report


def status_of(stack: Stack, parent: str) -> dict:
    return stack.api.get(f"/api/batches/{parent}/followups")


def row(report: dict, key: str) -> dict:
    return next(item for item in report["steps"] if item["step"] == key)


def remove(stack: Stack, parent: str, step_key: str, version: int) -> tuple:
    return stack.api.raw(
        "DELETE",
        f"/api/batches/{parent}/followups/{step_key}?confirm=true&version={version}",
    )


def retire(stack: Stack, parent: str, step_key: str, version: int) -> tuple:
    return stack.api.raw(
        "POST",
        f"/api/batches/{parent}/followups/{step_key}/retire"
        f"?confirm=true&version={version}",
    )


def cli(stack: Stack, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "downcroc", *args],
        cwd=ROOT,
        env=stack.daemon.environment(),
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


def cli_json(stack: Stack, *args: str):
    result = cli(stack, *args)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)
