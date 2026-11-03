from __future__ import annotations

import hashlib
import hmac
import io
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx
from packaging.version import InvalidVersion, Version
from rich.console import Console
from rich.markdown import Markdown
from rich.theme import Theme

from downcroc.cli.context import load
from downcroc.cli.errors import CliError
from downcroc.cli.install_layout import install_prefix
from downcroc.cli.output import json_out, record
from downcroc.cli.ui import panel
from downcroc.runtime.service.lifecycle import start, status, stop
from downcroc.version import __version__

API = "https://api.github.com/repos/Logisite/downcroc/releases"
NOTES_THEME = Theme(
    {
        "markdown.h1": "bold orange3",
        "markdown.h2": "bold orange3",
        "markdown.h3": "bold orange3",
        "markdown.h4": "bold orange3",
        "markdown.h5": "bold orange3",
        "markdown.h6": "bold orange3",
    }
)


def _version(value: str) -> Version:
    text = value.strip().lstrip("vV")
    try:
        return Version(text)
    except InvalidVersion as error:
        raise CliError(f"invalid version: {value}", code="version_invalid") from error


def _releases(*, pre: bool) -> list[dict]:
    response = httpx.get(
        API,
        params={"per_page": 30},
        headers={"Accept": "application/vnd.github+json", "User-Agent": "downcroc"},
        timeout=20,
        trust_env=True,
    )
    if response.status_code != 200:
        raise CliError(
            "the release feed could not be read",
            code="release_feed_failed",
            hint=f"github returned {response.status_code}",
        )
    found = [
        item
        for item in response.json()
        if not item.get("draft") and (pre or not item.get("prerelease"))
    ]
    return found


def _release(version: str | None, *, pre: bool) -> dict:
    releases = _releases(pre=pre)
    if version is not None:
        wanted = _version(version)
        for item in releases:
            if _version(item["tag_name"]) == wanted:
                return item
        raise CliError(
            f"release {version} was not found",
            code="release_not_found",
            hint="run downcroc update --check --pre to list available releases",
        )
    if not releases:
        raise CliError("no release is available", code="release_not_found")
    return max(releases, key=lambda item: _version(item["tag_name"]))


def _wheel(release: dict, directory: Path) -> tuple[Path, str | None]:
    assets = release.get("assets") or []
    asset = next(
        (item for item in assets if str(item.get("name", "")).endswith(".whl")),
        None,
    )
    if asset is None:
        raise CliError("the release has no wheel", code="release_invalid")
    response = httpx.get(
        asset["browser_download_url"],
        headers={"User-Agent": "downcroc"},
        timeout=60,
        follow_redirects=True,
        trust_env=True,
    )
    if response.status_code != 200:
        raise CliError(
            "the wheel could not be downloaded",
            code="download_failed",
            hint=f"github returned {response.status_code}",
        )
    name = Path(str(asset.get("name") or "downcroc.whl")).name
    if not name.endswith(".whl"):
        name = "downcroc.whl"
    target = directory / name
    target.write_bytes(response.content)
    digest = asset.get("digest") or ""
    expected = digest.split(":", 1)[-1] if digest.startswith("sha256:") else None
    return target, expected


def _restart_after_update(paths, settings, ui) -> bool:
    was_running = status(paths).get("state") == "running"
    if was_running:
        if not ui.json_mode:
            print(ui.dim("stopping the daemon..."), flush=True)
        stop(paths, settings)
    return was_running


def _restart(
    paths,
    settings,
    was_running: bool,
    ui,
    *,
    no_restart: bool,
) -> None:
    if not was_running or no_restart:
        return
    if not ui.json_mode:
        print(ui.dim("starting the daemon..."), flush=True)
    start(paths, settings, timeout=settings.daemon.start_timeout_s)


def _notes(body: str, ui) -> None:
    if not body.strip() or ui.json_mode:
        return
    stream = io.StringIO()
    console = Console(
        file=stream,
        width=panel.content_width(ui),
        force_terminal=ui.colour,
        color_system="256" if ui.colour else None,
        theme=NOTES_THEME,
        highlight=False,
        emoji=False,
        soft_wrap=False,
    )
    console.print(Markdown(body))
    text = stream.getvalue().rstrip("\n")
    text = re.sub(r"\x1b\]8;;.*?\x1b\\", "", text)
    if not text:
        return
    print()
    for line in panel.frame(ui, "Release notes", text.splitlines()):
        print(line)


def _check(args: object, ui) -> int:
    current = __version__
    release = _release(getattr(args, "target_version", None), pre=args.pre)
    latest = str(release["tag_name"]).lstrip("vV")
    body = {
        "current": current,
        "latest": latest,
        "url": release.get("html_url"),
        "notes": release.get("body") or "",
    }
    if ui.json_mode:
        json_out(body)
        return 0
    record({"current": current, "latest": latest, "url": body["url"]})
    _notes(body["notes"], ui)
    return 0


def run(args: object) -> int:
    ui = build_ui(args)
    if getattr(args, "check", False):
        return _check(args, ui)
    release = _release(getattr(args, "target_version", None), pre=args.pre)
    latest = str(release["tag_name"]).lstrip("vV")
    current = __version__
    if not args.force and _version(latest) == _version(current):
        if ui.json_mode:
            json_out({"current": current, "latest": latest, "changed": False})
        else:
            record({"downcroc": current, "state": "up to date"})
        return 0
    if not args.force and _version(latest) < _version(current):
        raise CliError(
            "downgrades require --force",
            code="downgrade_refused",
            hint=f"run downcroc update --version {latest} --force",
        )
    prefix = install_prefix()
    if prefix is None:
        raise CliError(
            "this command must run from an installed downcroc",
            code="not_managed_install",
            hint="use scripts/install.sh or scripts/install.ps1",
        )
    paths, settings, _ = load()
    was_running = _restart_after_update(paths, settings, ui)
    try:
        with tempfile.TemporaryDirectory(prefix="downcroc-update-") as directory:
            wheel, expected = _wheel(release, Path(directory))
            if expected is not None:
                actual = hashlib.sha256(wheel.read_bytes()).hexdigest()
                if not hmac.compare_digest(actual, expected):
                    raise CliError(
                        "the wheel checksum does not match",
                        code="checksum_failed",
                    )
            command = [sys.executable, "-m", "pip", "install", "--upgrade"]
            if args.force:
                command.extend(["--force-reinstall", "--no-deps"])
            command.append(str(wheel))
            if ui.json_mode:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                code = result.returncode
                detail = (result.stderr or result.stdout).strip()
            else:
                print(ui.dim(f"installing downcroc {latest}..."), flush=True)
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                tail: list[str] = []
                if process.stdout is not None:
                    for line in process.stdout:
                        print(line, end="", flush=True)
                        tail.append(line)
                        if len(tail) > 40:
                            tail.pop(0)
                code = process.wait()
                detail = "".join(tail).strip()
            if code != 0:
                raise CliError(
                    "the update could not be installed",
                    code="update_failed",
                    hint=detail[-500:] or f"pip exited with {code}",
                )
    except BaseException:
        _restart(paths, settings, was_running, ui, no_restart=args.no_restart)
        raise
    _restart(paths, settings, was_running, ui, no_restart=args.no_restart)
    body = {
        "current": current,
        "installed": latest,
        "url": release.get("html_url"),
        "restarted": was_running and not args.no_restart,
    }
    if ui.json_mode:
        json_out(body)
        return 0
    record({"downcroc": latest, "previous": current})
    if body["restarted"]:
        record({"service": "restarted"})
    _notes(release.get("body") or "", ui)
    return 0


def build_ui(args: object):
    from downcroc.cli.ui.session import build

    return build(args)
