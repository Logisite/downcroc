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
def stack(tmp_path: Path) -> Stack:
    runtime = tmp_path / "runtime"
    fakes = FakeMailServers().start()
    daemon = Daemon(runtime)
    try:
        daemon.start(fakes)
        api = Api(daemon.base_url)
        api.unlock()
        accounts = connect_accounts(api, ["alice@local.test", "bob@local.test"])
        yield Stack(
            root=tmp_path,
            daemon=daemon,
            fakes=fakes,
            api=api,
            accounts=accounts,
        )
    finally:
        daemon.stop()
        fakes.stop()
