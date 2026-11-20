from __future__ import annotations

import json

from tests.harness.campaigns import input_files
from tests.harness.inbound import cli
from tests.harness.seed import write_json


def _run(stack, *args):
    return cli(stack, *args)


def test_validate_followup_one_shot_no_subject(stack_factory) -> None:
    """A subject-less one-shot payload is valid under --followup."""
    stack = stack_factory(accounts=[])
    path = write_json(
        input_files(stack),
        "one-shot.json",
        [{"to": {"email": "ana@example.com"}, "text": "Bump.\n"}],
    )
    result = _run(stack, "batch", "validate", str(path), "--followup", "--json")
    assert result.returncode == 0, result.stderr
    body = json.loads(result.stdout)
    assert body["ok"] is True
    assert body["kind"] == "followup"
    assert body["mode"] == "one-shot"
    assert body["schedule"] is None
    assert "subject" in " ".join(body["auto"])


def test_validate_followup_scheduled(stack_factory) -> None:
    """A scheduled payload declaration validates with its schedule."""
    stack = stack_factory(accounts=[])
    path = write_json(
        input_files(stack),
        "scheduled.json",
        {
            "followup": {
                "after_days": 3,
                "when": "no_reply",
                "require_approval": False,
            },
            "messages": [
                {
                    "key": "m1",
                    "to": {"email": "ana@example.com"},
                    "text": "Following up.\n",
                }
            ],
        },
    )
    result = _run(stack, "batch", "validate", str(path), "--followup", "--json")
    assert result.returncode == 0, result.stderr
    body = json.loads(result.stdout)
    assert body["ok"] is True
    assert body["mode"] == "scheduled"
    assert body["schedule"]["after_days"] == 3


def test_validate_followup_scheduled_requires_schedule(stack_factory) -> None:
    """A scheduled payload with an invalid after_days is rejected."""
    stack = stack_factory(accounts=[])
    path = write_json(
        input_files(stack),
        "bad.json",
        {
            "followup": {"after_days": 0},
            "messages": [{"to": {"email": "ana@example.com"}, "text": "x"}],
        },
    )
    result = _run(stack, "batch", "validate", str(path), "--followup", "--json")
    assert result.returncode == 1, result.stdout
    body = json.loads(result.stdout)
    assert body["ok"] is False
    assert body["kind"] == "followup"


def test_validate_campaign_hints_followup(stack_factory) -> None:
    """Campaign validation points a subject-less file at --followup."""
    stack = stack_factory(accounts=[])
    path = write_json(
        input_files(stack),
        "campaign.json",
        [{"to": {"email": "ana@example.com"}, "text": "Bump.\n"}],
    )
    result = _run(stack, "batch", "validate", str(path), "--json")
    assert result.returncode == 1, result.stdout
    body = json.loads(result.stdout)
    assert body["ok"] is False
    assert "batch validate --followup" in body["hint"]


def test_stack_flag_is_global(stack_factory) -> None:
    """--stack and --grid work before or after the command."""
    stack = stack_factory(accounts=[])
    result = _run(stack, "batch", "list", "--stack", "--json")
    assert result.returncode == 0, result.stderr
    result = _run(stack, "batch", "list", "--grid", "--json")
    assert result.returncode == 0, result.stderr

    stacked = _run(stack, "--stack", "batch", "list")
    assert stacked.returncode == 0, stacked.stderr
    assert "no batches match" in stacked.stdout
    assert "╭" not in stacked.stdout

    gridded = _run(stack, "--grid", "--stack", "batch", "list")
    assert gridded.returncode == 0, gridded.stderr
    assert "╭" in gridded.stdout
