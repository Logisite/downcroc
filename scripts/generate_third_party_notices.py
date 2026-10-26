from __future__ import annotations

import argparse
import sys
import tomllib
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "uv.lock"
NOTICES = ROOT / "THIRD_PARTY_NOTICES.md"
HEADER = """# Third-party notices

downcroc is distributed under the Apache License, Version 2.0. It depends on
the following third-party packages. Each package remains under its own licence.
The full licence text is shipped with the installed distribution and is also
available from the package metadata on PyPI.

| Package | Licence | Project |
|---|---|---|
"""
CLASSIFIER_LICENCES = {
    "License :: OSI Approved :: Apache Software License": "Apache-2.0",
    "License :: OSI Approved :: BSD License": "BSD-3-Clause",
    "License :: OSI Approved :: MIT License": "MIT",
    "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0",
    "License :: OSI Approved :: Python Software Foundation License": "PSF-2.0",
}


def _lock_packages() -> dict[str, dict]:
    data = tomllib.loads(LOCK.read_text(encoding="utf-8"))
    return {package["name"].lower(): package for package in data["package"]}


def _runtime_closure(packages: dict[str, dict]) -> list[dict]:
    root = packages["downcroc"]
    pending = [dependency["name"] for dependency in root["dependencies"]]
    seen: set[str] = set()
    closure: list[dict] = []
    while pending:
        name = pending.pop().lower()
        if name in seen:
            continue
        seen.add(name)
        package = packages[name]
        closure.append(package)
        pending.extend(
            dependency["name"] for dependency in package.get("dependencies", [])
        )
    return sorted(closure, key=lambda package: package["name"].lower())


def _licence(package: dict) -> str:
    distribution = metadata.distribution(package["name"])
    installed = distribution.version
    if installed != package["version"]:
        raise SystemExit(
            f"{package['name']} is installed at {installed}, "
            f"but uv.lock has {package['version']}"
        )
    expression = distribution.metadata.get("License-Expression")
    if expression:
        return expression
    for classifier in distribution.metadata.get_all("Classifier") or []:
        if classifier in CLASSIFIER_LICENCES:
            return CLASSIFIER_LICENCES[classifier]
    text = (distribution.metadata.get("License") or "").strip().splitlines()
    if text and len(text[0]) <= 80:
        return text[0]
    return "See package metadata"


def render() -> str:
    packages = _lock_packages()
    lines = [HEADER.rstrip("\n")]
    for package in _runtime_closure(packages):
        name = package["name"]
        lines.append(
            f"| {name} | {_licence(package)} | https://pypi.org/project/{name}/ |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate third-party licence notices")
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail when the committed file differs from the generated output",
    )
    args = parser.parse_args(argv)
    rendered = render()
    if args.check:
        if not NOTICES.is_file() or NOTICES.read_text(encoding="utf-8") != rendered:
            print(
                f"{NOTICES.name} is out of date; run "
                f"uv run python {Path(__file__).resolve().relative_to(ROOT)}",
                file=sys.stderr,
            )
            return 1
        return 0
    NOTICES.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
