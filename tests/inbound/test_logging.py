from __future__ import annotations

from tests.harness.gmail import FakeGmail
from tests.harness.logs import events


def test_oauth_cancel_on_archive_names_the_account(stack_factory) -> None:
    gmail = FakeGmail().start()
    try:
        stack = stack_factory(
            accounts=[],
            extra_providers=lambda fakes: gmail.provider_toml(fakes),
        )
        account = stack.api.create_account("gmail@local.test", provider="gmail")
        attempt = stack.api.post(f"/api/accounts/{account['id']}/attempts")
        stack.api.post(f"/api/accounts/{account['id']}/archive?confirm=true")

        cancelled = events(stack)["oauth.cancelled"][-1]
        assert cancelled["attempt"] == attempt["id"]
        assert cancelled["account"] == account["id"]
        assert cancelled["cause"] == "account_stop"
    finally:
        gmail.stop()


def test_watcher_stop_names_cause_and_context(stack_factory) -> None:
    stack = stack_factory(accounts=["alice@local.test"])
    alice = stack.accounts[0]
    stack.daemon.stop()

    stopped = events(stack)["watcher.stopped"][-1]
    assert stopped["account"] == alice
    assert stopped["cause"]
    assert stopped["reason"]
    assert stopped["host"]
    assert isinstance(stopped["uid"], int)
    assert isinstance(stopped["attempt"], int)
