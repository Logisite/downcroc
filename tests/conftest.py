from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.harness.api import Api
from tests.harness.daemon import Daemon
from tests.harness.fakes import FakeMailServers
from tests.harness.seed import connect_accounts


@dataclass
class Stack:
    root: Path
    daemon: Daemon
    fakes: FakeMailServers
    api: Api
    accounts: list[str]


@pytest.fixture
def stack_factory(tmp_path: Path):
    created: list[Stack] = []

    def make(
        *,
        config_extra: str = "",
        accounts: list[str] | None = None,
    ) -> Stack:
        runtime = tmp_path / f"runtime-{len(created)}"
        fakes = FakeMailServers().start()
        daemon = Daemon(runtime)
        daemon.start(fakes, config_extra)
        api = Api(daemon.base_url, daemon.state_home / "downcroc" / "daemon.token")
        api.unlock()
        connected = connect_accounts(
            api,
            accounts or ["alice@local.test", "bob@local.test"],
        )
        stack = Stack(
            root=runtime,
            daemon=daemon,
            fakes=fakes,
            api=api,
            accounts=connected,
        )
        created.append(stack)
        return stack

    yield make
    for stack in created:
        stack.daemon.stop()
        stack.fakes.stop()


@pytest.fixture
def stack(stack_factory) -> Stack:
    return stack_factory()
