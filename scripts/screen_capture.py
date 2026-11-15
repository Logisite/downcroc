"""Capture the book's interactive screens from a real, fully seeded daemon.

This is the persistence layer for screen truth. It boots the real daemon
against the real test-harness fake mail servers, connects mailboxes, drives a
real batch through dispatch (two delivered, one refused with a genuine
``smtp_550``), and then records the interactive screens the book quotes. The
captures and a manifest land under ``src/downcroc/docs/assets/screens`` and
are committed, so a page that quotes a screen never has to be re-derived by
hand.

Usage:
    uv run python scripts/screen_capture.py           # (re)capture all
    uv run python scripts/screen_capture.py --check   # exit 1 on drift
    uv run python scripts/screen_capture.py --list    # the named screens
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from probe_terminal import Pty, Screen

from tests.harness.api import Api
from tests.harness.daemon import Daemon
from tests.harness.dispatch import dispatch_config
from tests.harness.fakes import FakeMailServers
from tests.harness.seed import campaign, connect_accounts, message, until, write_json

OUT = REPO / "src" / "downcroc" / "docs" / "assets" / "screens"
COLUMNS = 66
ROWS = 24

# name -> (argv inside the interactive cli, keys to press after ready)
SCREENS: dict[str, tuple[list[str], str]] = {
    "home-menu": ([], "q"),
    "status-panel": (["status"], "q"),
    "failed-list": (["failed", "list"], "r | q | y"),
}


def boot(root: Path) -> tuple[FakeMailServers, Daemon, Api, list[str]]:
    fakes = FakeMailServers().start()
    daemon = Daemon(root)
    daemon.start(
        fakes,
        config_extra=dispatch_config(window_start=0, window_end=24),
    )
    api = Api(daemon.base_url, daemon.state_home / "downcroc" / "daemon.token")
    api.unlock()
    accounts = connect_accounts(api, ["alice@local.test", "bob@local.test"])
    return fakes, daemon, api, accounts


def seed_work(api: Api, root: Path) -> dict[str, object]:
    inputs = root / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    path = write_json(
        inputs,
        "campaign.json",
        campaign(
            [
                message("ana@example.com", key="m1", name="Ana", subject="Weekly note"),
                message("sam@example.com", key="m2", name="Sam", subject="Weekly note"),
                message(
                    "permanent@example.com",
                    key="m3",
                    name="Refused",
                    subject="Weekly note",
                ),
            ],
            options={"approval": "auto"},
        ),
    )
    batch = api.submit(str(path))
    until(
        lambda: api.get(f"/api/batches/{batch['id']}")["state"] == "done",
        timeout=240,
    )
    failures = api.get("/api/failed")
    if not failures:
        raise RuntimeError("the seed batch produced no failure rows")
    return {
        "batch": batch["id"],
        "sent": 2,
        "failed": len(failures),
        "codes": sorted({failure["code"] for failure in failures}),
    }


def capture(daemon: Daemon, argv: list[str], keys: str) -> str:
    env = daemon.environment()
    env.update({"NO_COLOR": "1", "TERM": "xterm-256color"})
    terminal = Pty(
        [sys.executable, "-m", "downcroc", "--glyphs", "ascii", *argv],
        env=env,
        cwd=str(REPO),
        rows=ROWS,
        columns=COLUMNS,
    )
    terminal.start()
    terminal.wait_ready()
    terminal.pump(idle=0.3, limit=2)
    for step in _steps(keys):
        terminal.send(step, idle=1.5, limit=30)
    terminal.pump(idle=0.4, limit=5)
    text = _frame(terminal.screen)
    terminal.close()
    return text


def _steps(keys: str) -> list[bytes]:
    from probe_terminal import parse_steps

    return [step.keys for step in parse_steps(keys)]


def _frame(screen: Screen) -> str:
    rows = screen.lines()
    width = max((len(line) for line in rows), default=0)
    lines = ["┌" + "─" * width + "┐"]
    lines.extend("│" + line.ljust(width) + "│" for line in rows)
    lines.append("└" + "─" * width + "┘")
    return "\n".join(lines) + "\n"


def write_all(runtime: Path) -> dict[str, object]:
    fakes, daemon, api, _accounts = boot(runtime)
    try:
        facts = seed_work(api, runtime)
        OUT.mkdir(parents=True, exist_ok=True)
        captured = {}
        for name, (argv, keys) in SCREENS.items():
            text = capture(daemon, argv, keys)
            (OUT / f"{name}.txt").write_text(text)
            captured[name] = text
        manifest = {
            "generated_at": datetime.datetime.now(datetime.UTC).isoformat(
                timespec="seconds"
            ),
            "columns": COLUMNS,
            "screens": sorted(SCREENS),
            "facts": facts,
        }
        (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        return {"facts": facts, "captured": captured}
    finally:
        daemon.stop()
        fakes.stop()


def check(runtime: Path) -> int:
    result = write_all(runtime)
    drifted = []
    for name in SCREENS:
        path = OUT / f"{name}.txt"
        if path.read_text() != result["captured"][name]:
            drifted.append(name)
    if drifted:
        print("drifted screens: " + ", ".join(drifted))
        return 1
    print("all screens match")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check", action="store_true", help="recapture and diff, exit 1 on drift"
    )
    parser.add_argument("--list", action="store_true", help="list named screens")
    args = parser.parse_args()
    if args.list:
        for name, (argv, _) in SCREENS.items():
            print(f"{name:16} downcroc {' '.join(argv)}".rstrip())
        return 0
    root = Path(os.environ.get("DOWNCROC_SCREEN_FIXTURE", "/tmp/opencode/fixture"))
    root.mkdir(parents=True, exist_ok=True)
    runtime = root / "runtime"
    shutil.rmtree(runtime, ignore_errors=True)
    runtime.mkdir(parents=True, exist_ok=True)
    if args.check:
        return check(runtime)
    result = write_all(runtime)
    print(json.dumps(result["facts"], indent=2))
    for name in SCREENS:
        print()
        print(f"{name}:")
        show_text = (OUT / f"{name}.txt").read_text()
        print("\n".join(f"    {line}" for line in show_text.splitlines()))
    return 0


if __name__ == "__main__":
    start = time.monotonic()
    sys.exit(main())
