from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.harness.api import Api
from tests.harness.daemon import Daemon
from tests.harness.diagnostics import describe
from tests.harness.fakes import FakeMailServers
from tests.harness.seed import connect_accounts


@dataclass
class Stack:
    root: Path
    daemon: Daemon
    fakes: FakeMailServers
    api: Api
    accounts: list[str]


_CREATED: list[Stack] = []


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    report = yield
    if report.failed and report.when == "call" and _CREATED:
        report.sections.append(
            ("downcroc diagnostics", "\n\n".join(describe(stack) for stack in _CREATED))
        )
    return report


@pytest.fixture
def stack_factory(tmp_path: Path):
    created: list[Stack] = []
    _CREATED.clear()

    def make(
        *,
        config_extra: str = "",
        accounts: list[str] | None = None,
        extra_providers: str | Callable[[FakeMailServers], str] = "",
    ) -> Stack:
        runtime = tmp_path / f"runtime-{len(created)}"
        fakes = FakeMailServers().start()
        daemon = Daemon(runtime)
        extra = extra_providers(fakes) if callable(extra_providers) else extra_providers
        daemon.start(fakes, config_extra, extra_providers=extra)
        api = Api(daemon.base_url, daemon.state_home / "downcroc" / "daemon.token")
        api.unlock()
        chosen = (
            ["alice@local.test", "bob@local.test"] if accounts is None else accounts
        )
        connected = connect_accounts(api, chosen)
        stack = Stack(
            root=runtime,
            daemon=daemon,
            fakes=fakes,
            api=api,
            accounts=connected,
        )
        created.append(stack)
        _CREATED.append(stack)
        return stack

    yield make
    for stack in created:
        stack.daemon.stop()
        stack.fakes.stop()
    _CREATED.clear()


@pytest.fixture
def stack(stack_factory) -> Stack:
    return stack_factory()
