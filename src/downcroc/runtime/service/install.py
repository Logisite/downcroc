from __future__ import annotations

import shutil
import subprocess

from downcroc.runtime.config.schema import Settings
from downcroc.runtime.fs import restrict
from downcroc.runtime.paths import Paths, ensure
from downcroc.runtime.service import units
from downcroc.runtime.service.lifecycle import stop


class ServiceError(RuntimeError):
    pass


def _write(plan: units.Plan) -> None:
    plan.path.parent.mkdir(parents=True, exist_ok=True)
    temporary = plan.path.with_suffix(plan.path.suffix + ".tmp")
    if plan.encoding == "utf-16":
        temporary.write_bytes(plan.definition.encode("utf-16"))
    else:
        temporary.write_text(plan.definition, encoding="utf-8", newline="\n")
    restrict(temporary, 0o600)
    temporary.replace(plan.path)


def _run(step: units.Step) -> None:
    try:
        completed = subprocess.run(
            step.argv,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as error:
        if step.ignore_failure:
            return
        raise ServiceError(f"command not found: {step.argv[0]}") from error
    if completed.returncode == 0 or step.ignore_failure:
        return
    detail = completed.stderr.strip() or completed.stdout.strip()
    raise ServiceError(f"{' '.join(step.argv)} failed: {detail}")


def _require_tools(plan: units.Plan) -> None:
    missing = [
        step.argv[0]
        for step in plan.install_steps
        if shutil.which(step.argv[0]) is None
    ]
    if missing:
        raise ServiceError(
            f"required command not found: {', '.join(sorted(set(missing)))}"
        )


def install(paths: Paths, settings: Settings, print_only: bool = False) -> dict:
    plan = units.build_plan(paths)
    if print_only:
        return units.describe(plan)
    _require_tools(plan)
    ensure(paths)
    if plan.platform == "macos":
        (paths.state / "logs").mkdir(parents=True, exist_ok=True)
    stopped = stop(paths, settings)
    _write(plan)
    for step in plan.install_steps:
        _run(step)
    return {
        "installed": True,
        "platform": plan.platform,
        "kind": plan.kind,
        "path": str(plan.path),
        "stopped_existing": stopped,
    }


def installed(paths: Paths) -> bool:
    return units.build_plan(paths).path.exists()


def uninstall(paths: Paths, settings: Settings) -> dict:
    plan = units.build_plan(paths)
    for step in plan.uninstall_steps:
        _run(step)
    stopped = stop(paths, settings)
    existed = plan.path.exists()
    if existed:
        plan.path.unlink()
    if plan.reload_step is not None and shutil.which(plan.reload_step.argv[0]):
        _run(plan.reload_step)
    return {
        "uninstalled": True,
        "platform": plan.platform,
        "kind": plan.kind,
        "path": str(plan.path),
        "removed": existed,
        "stopped_existing": stopped,
    }
