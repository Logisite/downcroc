from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

from downcroc.runtime.paths import Paths

LABEL = "com.downcroc.daemon"
TASK_NAME = "downcroc"
SYSTEMD_NAME = "downcroc.service"


@dataclass(frozen=True)
class Step:
    argv: tuple[str, ...]
    ignore_failure: bool = False


@dataclass(frozen=True)
class Plan:
    platform: str
    kind: str
    path: Path
    definition: str
    encoding: str
    install_steps: tuple[Step, ...]
    uninstall_steps: tuple[Step, ...]
    reload_step: Step | None = None


def launcher() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable]
    script = Path(sys.argv[0])
    try:
        resolved = script.resolve()
    except OSError:
        resolved = script
    if resolved.exists() and resolved.name.lower().startswith("downcroc"):
        return [str(resolved)]
    return [sys.executable, "-m", "downcroc"]


def _home() -> Path:
    value = os.environ.get("HOME") or os.environ.get("USERPROFILE")
    return Path(value) if value else Path(os.path.expanduser("~"))


def _xdg(name: str) -> str | None:
    value = os.environ.get(name)
    return value or None


def _environment() -> dict[str, str]:
    values = {"HOME": str(_home())}
    for name in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME"):
        value = _xdg(name)
        if value:
            values[name] = value
    return values


def definition_path(paths: Paths) -> Path:
    if sys.platform == "win32":
        return paths.state / "service-task.xml"
    if sys.platform == "darwin":
        return _home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
    config = Path(_xdg("XDG_CONFIG_HOME") or _home() / ".config")
    return config / "systemd" / "user" / SYSTEMD_NAME


def build_plan(paths: Paths) -> Plan:
    if sys.platform == "win32":
        return _windows(paths)
    if sys.platform == "darwin":
        return _launchd(paths)
    return _systemd(paths)


def _systemd_quote(value: str, specifiers: bool = True) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    if specifiers:
        escaped = escaped.replace("%", "%%")
    return f'"{escaped}"'


def _systemd(paths: Paths) -> Plan:
    command = launcher() + ["serve"]
    lines = [
        "[Unit]",
        "Description=downcroc local mail daemon",
        "Documentation=https://github.com/Logisite/downcroc",
        "",
        "[Service]",
        "Type=simple",
        "ExecStart=" + " ".join(_systemd_quote(item) for item in command),
        f"WorkingDirectory={_systemd_quote(str(_home()))}",
        "Restart=on-failure",
        "RestartSec=2",
        "TimeoutStopSec=20",
        "KillMode=mixed",
    ]
    for name, value in _environment().items():
        assignment = f"{name}={value}"
        lines.append(f"Environment={_systemd_quote(assignment, specifiers=False)}")
    lines.extend(
        [
            "",
            "[Install]",
            "WantedBy=default.target",
            "",
        ]
    )
    unit = "\n".join(lines)
    path = definition_path(paths)
    return Plan(
        platform="linux",
        kind="systemd-user-unit",
        path=path,
        definition=unit,
        encoding="utf-8",
        install_steps=(
            Step(("systemctl", "--user", "daemon-reload")),
            Step(("systemctl", "--user", "enable", "--now", SYSTEMD_NAME)),
        ),
        uninstall_steps=(
            Step(
                ("systemctl", "--user", "disable", "--now", SYSTEMD_NAME),
                ignore_failure=True,
            ),
        ),
        reload_step=Step(("systemctl", "--user", "daemon-reload")),
    )


def _launchd(paths: Paths) -> Plan:
    command = launcher() + ["serve"]
    logs = paths.state / "logs"
    payload = {
        "Label": LABEL,
        "ProgramArguments": command,
        "WorkingDirectory": str(_home()),
        "EnvironmentVariables": _environment(),
        "RunAtLoad": True,
        "KeepAlive": {"SuccessfulExit": False},
        "ProcessType": "Background",
        "StandardOutPath": str(logs / "launchd.out"),
        "StandardErrorPath": str(logs / "launchd.err"),
    }
    definition = plistlib.dumps(payload, sort_keys=True).decode("utf-8")
    path = definition_path(paths)
    uid = os.getuid() if hasattr(os, "getuid") else 0
    domain = f"gui/{uid}"
    return Plan(
        platform="macos",
        kind="launchd-agent",
        path=path,
        definition=definition,
        encoding="utf-8",
        install_steps=(
            Step(("launchctl", "bootout", domain, str(path)), ignore_failure=True),
            Step(("launchctl", "bootstrap", domain, str(path))),
        ),
        uninstall_steps=(
            Step(("launchctl", "bootout", domain, str(path)), ignore_failure=True),
        ),
    )


def _windows_user() -> str:
    user = os.environ.get("USERNAME") or os.environ.get("USER") or "user"
    domain = os.environ.get("USERDOMAIN")
    return f"{domain}\\{user}" if domain else user


def _windows(paths: Paths) -> Plan:
    command = launcher() + ["serve"]
    arguments = subprocess.list2cmdline(command[1:]) if len(command) > 1 else ""
    user = _windows_user()
    definition = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>downcroc local mail daemon</Description>
    <URI>\\{TASK_NAME}</URI>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <UserId>{escape(user)}</UserId>
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>{escape(user)}</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Enabled>true</Enabled>
    <Hidden>true</Hidden>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{escape(command[0])}</Command>
      <Arguments>{escape(arguments)}</Arguments>
      <WorkingDirectory>{escape(str(_home()))}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""
    path = definition_path(paths)
    return Plan(
        platform="windows",
        kind="scheduled-task",
        path=path,
        definition=definition,
        encoding="utf-16",
        install_steps=(
            Step(("schtasks", "/End", "/TN", TASK_NAME), ignore_failure=True),
            Step(("schtasks", "/Create", "/TN", TASK_NAME, "/XML", str(path), "/F")),
        ),
        uninstall_steps=(
            Step(("schtasks", "/End", "/TN", TASK_NAME), ignore_failure=True),
            Step(
                ("schtasks", "/Delete", "/TN", TASK_NAME, "/F"),
                ignore_failure=True,
            ),
        ),
    )


def describe(plan: Plan) -> dict[str, object]:
    return {
        "platform": plan.platform,
        "kind": plan.kind,
        "path": str(plan.path),
        "definition": plan.definition,
        "install": [list(step.argv) for step in plan.install_steps],
        "uninstall": [list(step.argv) for step in plan.uninstall_steps],
    }
