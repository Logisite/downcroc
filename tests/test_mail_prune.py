from __future__ import annotations

from tests.conftest import Stack
from tests.harness.inbound import cli_json
from tests.harness.replies import (
    account_address,
    deliver_reply,
    messages,
    sync_and_wait,
)


def test_mail_prune_removes_inbox_copies_of_own_mail(stack_factory) -> None:
    stack: Stack = stack_factory(accounts=["alice@local.test"])
    account = stack.accounts[0]
    address = account_address(stack, account)

    deliver_reply(
        stack.fakes,
        to_address=address,
        from_address=address,
        subject="A copy of my own message",
        message_id="self-copy@example.com",
    )
    sync_and_wait(stack, account, 1)
    assert [row["message_id"] for row in messages(stack, account)] == [
        "self-copy@example.com"
    ]

    preview = cli_json(stack, "mail", "prune", "--dry-run", "--json")
    assert preview["dry_run"] is True
    assert preview["messages"] == 1
    assert messages(stack, account)

    removed = cli_json(stack, "mail", "prune", "--yes", "--json")
    assert removed["dry_run"] is False
    assert removed["messages"] == 1
    assert messages(stack, account) == []
