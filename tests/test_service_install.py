from __future__ import annotations

import json
import os
import plistlib
import shlex
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree

import pytest

ROOT = Path(__file__).resolve().parents[1]
TASK_NS = {"task": "http://schemas.microsoft.com/windows/2004/02/mit/task"}


def _env(root: Path, path_prefix: Path | None = None) -> dict[str, str]:
    for name in ("home", "config", "data", "state"):
        (root / name).mkdir(parents=True, exist_ok=True)
    env = {
        **os.environ,
        "HOME": str(root / "home"),
        "XDG_CONFIG_HOME": str(root / "config"),
        "XDG_DATA_HOME": str(root / "data"),
        "XDG_STATE_HOME": str(root / "state"),
        "NO_COLOR": "1",
    }
    if path_prefix is not None:
        env["PATH"] = f"{path_prefix}{os.pathsep}{env.get('PATH', '')}"
    return env


def _run(
    args: list[str],
    env: dict[str, str],
    executable: str | None = None,
) -> subprocess.CompletedProcess[str]:
    command = (
        [executable, *args] if executable else [sys.executable, "-m", "downcroc", *args]
    )
    return subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def _json(proc: subprocess.CompletedProcess[str]) -> dict:
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def _stub(bin_dir: Path, name: str, log: Path) -> None:
    script = bin_dir / name
    script.write_text(
        f"#!/bin/sh\nprintf '%s\\n' \"$*\" >> {shlex.quote(str(log))}\nexit 0\n"
    )
    script.chmod(0o755)


def test_print_renders_the_platform_definition(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    env = _env(root)
    report = _json(_run(["service", "install", "--print", "--json"], env))
    definition = report["definition"]
    assert report["path"].startswith(str(root))
    assert "sudo" not in definition
    assert not Path(report["path"]).exists()
    if sys.platform == "win32":
        _assert_windows_definition(definition, report)
    elif sys.platform == "darwin":
        _assert_macos_definition(definition, report, root)
    else:
        _assert_linux_definition(definition, report, root)


def _assert_linux_definition(definition: str, report: dict, root: Path) -> None:
    assert report["platform"] == "linux"
    assert report["path"] == str(
        root / "config" / "systemd" / "user" / "downcroc.service"
    )
    assert "[Install]\nWantedBy=default.target" in definition
    assert "User=" not in definition
    start = next(
        line for line in definition.splitlines() if line.startswith("ExecStart=")
    )
    assert start.endswith('"serve"')
    assert str(Path(sys.executable)) in start
    assert f'Environment="XDG_CONFIG_HOME={root / "config"}"' in definition
    assert report["install"][0] == ["systemctl", "--user", "daemon-reload"]
    assert report["install"][1] == [
        "systemctl",
        "--user",
        "enable",
        "--now",
        "downcroc.service",
    ]


def _assert_macos_definition(definition: str, report: dict, root: Path) -> None:
    assert report["platform"] == "macos"
    path = root / "home" / "Library" / "LaunchAgents" / "com.downcroc.daemon.plist"
    assert report["path"] == str(path)
    payload = plistlib.loads(definition.encode("utf-8"))
    assert payload["Label"] == "com.downcroc.daemon"
    assert payload["RunAtLoad"] is True
    assert payload["ProgramArguments"][-1] == "serve"
    assert Path(payload["ProgramArguments"][0]).is_absolute()
    assert payload["WorkingDirectory"] == str(root / "home")
    assert payload["StandardOutPath"].startswith(str(root / "state"))
    assert "UserName" not in payload
    assert "sudo" not in " ".join(report["install"][0])


def _assert_windows_definition(definition: str, report: dict) -> None:
    assert report["platform"] == "windows"
    tree = ElementTree.fromstring(definition.encode("utf-16"))
    trigger = tree.find("task:Triggers/task:LogonTrigger", TASK_NS)
    assert trigger is not None
    principal = tree.find("task:Principals/task:Principal", TASK_NS)
    assert principal is not None
    assert principal.findtext("task:RunLevel", namespaces=TASK_NS) == "LeastPrivilege"
    assert (
        principal.findtext("task:LogonType", namespaces=TASK_NS) == "InteractiveToken"
    )
    command = tree.findtext("task:Actions/task:Exec/task:Command", namespaces=TASK_NS)
    assert command is not None and Path(command).is_absolute()
    arguments = tree.findtext(
        "task:Actions/task:Exec/task:Arguments", namespaces=TASK_NS
    )
    assert arguments is not None and arguments.endswith("serve")
    assert "HighestAvailable" not in definition
    assert "/RU" not in report["definition"]


@pytest.mark.skipif(sys.platform != "linux", reason="systemd user units")
def test_linux_install_is_idempotent_and_preserves_data(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "systemctl.log"
    _stub(bin_dir, "systemctl", log)
    env = _env(root, path_prefix=bin_dir)
    first = _json(_run(["service", "install", "--json"], env))
    unit = Path(first["path"])
    assert first["installed"] is True
    assert unit == root / "config" / "systemd" / "user" / "downcroc.service"
    content = unit.read_text(encoding="utf-8")
    assert content.count("ExecStart=") == 1
    assert str(Path(sys.executable)) in content
    calls = log.read_text(encoding="utf-8")
    assert "--user daemon-reload" in calls
    assert "--user enable --now downcroc.service" in calls
    data = root / "data" / "downcroc" / "keep.txt"
    data.write_text("keep", encoding="utf-8")
    second = _json(_run(["service", "install", "--json"], env))
    assert second["path"] == first["path"]
    assert len(list(unit.parent.glob("*.service"))) == 1
    assert log.read_text(encoding="utf-8").count("enable --now downcroc.service") == 2
    removed = _json(_run(["service", "uninstall", "--json"], env))
    assert removed["removed"] is True
    assert not unit.exists()
    assert data.read_text(encoding="utf-8") == "keep"
    calls = log.read_text(encoding="utf-8")
    assert "--user disable --now downcroc.service" in calls
    assert calls.rstrip().endswith("--user daemon-reload")


@pytest.mark.skipif(sys.platform != "linux", reason="systemd user units")
def test_linux_install_updates_the_binary_path(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _stub(bin_dir, "systemctl", tmp_path / "systemctl.log")
    env = _env(root, path_prefix=bin_dir)
    launchers: list[Path] = []
    for name in ("first", "second"):
        place = tmp_path / name
        place.mkdir()
        script = place / "downcroc"
        script.write_text(
            f"#!{sys.executable}\n"
            "from downcroc.cli.main import main\n"
            "raise SystemExit(main())\n",
            encoding="utf-8",
        )
        script.chmod(0o755)
        launchers.append(script)
    _json(_run(["service", "install", "--json"], env, executable=str(launchers[0])))
    unit = root / "config" / "systemd" / "user" / "downcroc.service"
    assert f'"{launchers[0]}"' in unit.read_text(encoding="utf-8")
    _json(_run(["service", "install", "--json"], env, executable=str(launchers[1])))
    content = unit.read_text(encoding="utf-8")
    assert f'"{launchers[1]}"' in content
    assert str(launchers[0]) not in content
    assert content.count("ExecStart=") == 1


@pytest.mark.skipif(sys.platform != "darwin", reason="launchd agents")
def test_macos_install_and_uninstall(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "launchctl.log"
    _stub(bin_dir, "launchctl", log)
    env = _env(root, path_prefix=bin_dir)
    report = _json(_run(["service", "install", "--json"], env))
    plist = Path(report["path"])
    assert report["installed"] is True
    assert (
        plist
        == root / "home" / "Library" / "LaunchAgents" / "com.downcroc.daemon.plist"
    )
    payload = plistlib.loads(plist.read_bytes())
    assert payload["RunAtLoad"] is True
    assert (root / "state" / "downcroc" / "logs").is_dir()
    calls = log.read_text(encoding="utf-8")
    assert f"bootstrap gui/{os.getuid()} {plist}" in calls
    data = root / "data" / "downcroc" / "keep.txt"
    data.write_text("keep", encoding="utf-8")
    removed = _json(_run(["service", "uninstall", "--json"], env))
    assert removed["removed"] is True
    assert not plist.exists()
    assert data.read_text(encoding="utf-8") == "keep"
    assert f"bootout gui/{os.getuid()} {plist}" in log.read_text(encoding="utf-8")
