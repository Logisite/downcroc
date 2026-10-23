from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from tests.harness.seed import campaign, message, write_json

if TYPE_CHECKING:
    from tests.conftest import Stack


def input_files(stack: Stack) -> Path:
    root = stack.root / "inputs"
    root.mkdir(exist_ok=True)
    return root


def submit(stack: Stack, document: object, name: str = "campaign.json") -> dict:
    path = write_json(input_files(stack), name, document)
    return stack.api.submit(str(path))


def recipients(count: int) -> list[dict]:
    return [
        message(
            f"person{index}@example.com",
            key=f"m{index}",
            name=f"Person {index}",
            subject=f"Subject {index}",
        )
        for index in range(1, count + 1)
    ]


def campaign_of(count: int, **kwargs) -> dict:
    return campaign(recipients(count), **kwargs)
