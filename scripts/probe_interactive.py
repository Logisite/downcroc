"""Reusable pty harness for scripting interactive CLI workflows.

A story is a command plus an ordered list of keystrokes. The harness starts the
real CLI on a real pty, paints the bytes it returns into a screen buffer, and
prints the keystroke and the resulting screen after every step. It never
asserts; the human reads the screens and decides.

Story files live in ``probe_stories.py``. This module is the engine.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO

from probe_terminal import Pty, Step, parse_steps, show

REPO = Path(__file__).resolve().parents[1]
DEFAULT_HOME = Path("/tmp/opencode/downcroc-probe-home")


@dataclass(frozen=True)
class Story:
    name: str
    title: str
    argv: list[str]
    keys: str | list[Step]
    live: bool = False
    lock_vault: bool = False
    follow: list[str] = field(default_factory=list)

    def steps(self) -> list[Step]:
        return (
            list(self.keys)
            if not isinstance(self.keys, str)
            else parse_steps(self.keys)
        )


@dataclass
class Daemon:
    """A disposable daemon with two mailboxes, one of them archived."""

    home: Path
    port: int
    process: subprocess.Popen[bytes] | None = None
    log: BinaryIO | None = None

    @property
    def env(self) -> dict[str, str]:
        env = dict(os.environ)
        env.pop("CI", None)
        env.update(
            {
                "HOME": str(self.home),
                "XDG_CONFIG_HOME": "",
                "XDG_DATA_HOME": "",
                "XDG_STATE_HOME": "",
                "NO_COLOR": "1",
                "TERM": "xterm-256color",
                "PYTHONUNBUFFERED": "1",
            }
        )
        return env

    def cli(
        self,
        *args: str,
        stdin: bytes | None = None,
        check: bool = True,
    ) -> str:
        result = subprocess.run(
            [sys.executable, "-m", "downcroc", *args],
            cwd=str(REPO),
            check=False,
            env=self.env,
            input=stdin,
            capture_output=True,
        )
        text = result.stdout.decode("utf-8", "replace")
        error = result.stderr.decode("utf-8", "replace")
        print(f"$ downcroc {' '.join(args)}")
        if text.strip():
            print(text.rstrip())
        if error.strip():
            print(error.rstrip())
        if check and result.returncode != 0:
            raise RuntimeError(f"setup command failed: {' '.join(args)}")
        print()
        return text

    def start(self) -> None:
        write_config(self.home, self.port)
        self.log = (self.home / "daemon.log").open("wb")
        self.process = subprocess.Popen(
            [sys.executable, "-m", "downcroc", "serve"],
            cwd=str(REPO),
            env=self.env,
            stdout=self.log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        wait_health(self.port, self.process)
        self.cli("vault", "init", "--password-stdin", "--no-keyring", stdin=b"pass\n")
        fake = self.home / "fake-client.json"
        fake.write_text(json.dumps(FAKE_CLIENT))
        self.cli("provider", "credentials", "set", "gmail", "--client", str(fake))
        self._add("old@example.com", "Old mailbox", archive=True)
        self._add("new@example.com", "Primary mailbox")
        self._add("oauth@example.com", "OAuth mailbox", provider="gmail")

    def _add(
        self,
        address: str,
        label: str,
        archive: bool = False,
        provider: str = "gmail-app-password",
    ) -> None:
        text = self.cli(
            "account",
            "add",
            "--provider",
            provider,
            "--address",
            address,
            "--label",
            label,
            "--json",
        )
        account = json.loads(text)
        if archive:
            self.cli("account", "archive", account["id"], "--yes", "--json")

    def stop(self) -> None:
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
        if self.log is not None:
            self.log.close()


FAKE_CLIENT = {
    "installed": {
        "client_id": "1234567890-probe.apps.googleusercontent.com",
        "project_id": "probe-project",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_secret": "probe-secret",
        "redirect_uris": ["http://localhost"],
    }
}


def write_config(home: Path, port: int) -> None:
    config = home / ".config" / "downcroc" / "config.toml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(f"[daemon]\nport = {port}\n")


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def wait_health(port: int, process: subprocess.Popen[bytes]) -> None:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.monotonic() + 120
    url = f"http://127.0.0.1:{port}/api/health"
    last = ""
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("the daemon exited before it became healthy")
        try:
            with opener.open(url, timeout=2) as response:
                if response.status == 200:
                    return
        except OSError as error:
            last = str(error)
            time.sleep(0.2)
    raise RuntimeError(f"the daemon did not answer /api/health: {last}")


def prepare(home: Path) -> None:
    shutil.rmtree(home, ignore_errors=True)
    home.mkdir(parents=True, exist_ok=True)


def run_story(
    story: Story,
    *,
    home: Path,
    rows: int,
    columns: int,
) -> None:
    prepare(home)
    port = free_port()
    daemon = Daemon(home, port)
    if story.live:
        daemon.start()
        if story.lock_vault:
            daemon.cli("vault", "lock")
    else:
        write_config(home, port)
    argv = [
        sys.executable,
        "-m",
        "downcroc",
        "--glyphs",
        "ascii",
        *story.argv,
    ]
    terminal = Pty(
        argv,
        env=daemon.env,
        cwd=str(REPO),
        rows=rows,
        columns=columns,
    )
    print("=" * (columns - 12))
    print(f"{story.name}: {story.title}")
    print(f"$ downcroc {' '.join(story.argv)}")
    try:
        terminal.start()
        terminal.wait_ready()
        show(terminal.screen)
        for step in story.steps():
            print()
            print(f"keys: {step.label}    {step.keys!r}")
            if step.wait:
                time.sleep(step.wait)
                terminal.pump(idle=0.3, limit=2)
            else:
                terminal.send(step.keys, idle=1.5, limit=30)
            show(terminal.screen)
        terminal.pump(idle=0.4, limit=5)
        if terminal.alive():
            print()
            print("[still running]")
        else:
            print()
            print(f"[process exited {terminal.process.returncode}]")
    finally:
        terminal.close()
        for command in story.follow:
            daemon.cli(*shlex.split(command))
        daemon.stop()


def parser(book: dict[str, Story]) -> argparse.ArgumentParser:
    found = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  uv run python scripts/probe_stories.py --list\n"
            "  uv run python scripts/probe_stories.py unarchive\n"
            "  uv run python scripts/probe_interactive.py "
            '--argv "account" --keys "/list | enter | enter | r | b"\n'
        ),
    )
    found.add_argument("story", nargs="*", help="story names to run")
    found.add_argument("--list", action="store_true", help="list stories")
    found.add_argument("--all", action="store_true", help="run every story")
    found.add_argument("--argv", help="ad-hoc command after downcroc, e.g. 'account'")
    found.add_argument("--keys", help="ad-hoc keys, separated by |")
    found.add_argument("--keys-file", help="read ad-hoc keys from a file")
    found.add_argument("--live", action="store_true", help="start a fixture daemon")
    found.add_argument("--follow", action="append", default=[], help="run after")
    found.add_argument("--home", default=str(DEFAULT_HOME), help="isolated HOME")
    found.add_argument("--rows", type=int, default=36, help="terminal rows")
    found.add_argument("--columns", type=int, default=100, help="terminal columns")
    if book:
        found.epilog = (
            (found.epilog or "")
            + "\n\nstories:\n"
            + "\n".join(f"  {name:16} {item.title}" for name, item in book.items())
        )
    return found


def ad_hoc(args: argparse.Namespace) -> Story:
    keys = args.keys or ""
    if args.keys_file:
        keys += "\n" + Path(args.keys_file).read_text()
    if not keys.strip():
        raise SystemExit("--keys or --keys-file is required with --argv")
    return Story(
        name="adhoc",
        title=f"ad-hoc: {' '.join(shlex.split(args.argv))}",
        argv=shlex.split(args.argv),
        keys=keys,
        live=args.live,
        follow=list(args.follow),
    )


def main(book: dict[str, Story] | None = None) -> int:
    stories = book or {}
    args = parser(stories).parse_args()
    if args.list:
        names = list(stories)
        if not names:
            print("no stories; add one to scripts/probe_stories.py")
        for name in names:
            print(f"{name:16} {stories[name].title}")
        return 0
    if args.argv:
        chosen = [ad_hoc(args)]
    else:
        chosen = selected(args, stories)
    for story in chosen:
        run_story(
            story,
            home=Path(args.home),
            rows=args.rows,
            columns=args.columns,
        )
    return 0


def selected(args: argparse.Namespace, book: dict[str, Story]) -> list[Story]:
    names = list(book)
    if not names:
        raise SystemExit("no stories; edit scripts/probe_stories.py")
    if args.all:
        return [book[name] for name in names]
    wanted = args.story or [names[0]]
    unknown = [name for name in wanted if name not in names]
    if unknown:
        raise SystemExit(f"unknown story: {', '.join(unknown)}")
    return [book[name] for name in wanted]


if __name__ == "__main__":
    sys.exit(main())
