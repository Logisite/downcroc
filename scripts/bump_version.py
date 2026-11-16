#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOK_INDEXES = (
    ROOT / "src/downcroc/docs/release-notes/index.md",
    ROOT / "docs/release-notes/index.md",
)


def run(*args: str) -> str:
    result = subprocess.run(
        args,
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def set_version(version: str, *, frozen: bool = False) -> None:
    """Set the version in pyproject.toml and refresh uv.lock by default.

    ``uv version`` re-locks by default, but that fails on machines where the
    pinned interpreter is absent (for example after a Python minor upgrade).
    We do it in two explicit steps so the version is always applied and the
    lock refresh uses an interpreter that actually exists.
    """
    subprocess.run(["uv", "version", version, "--frozen"], cwd=ROOT, check=True)
    if frozen:
        return
    refresh_lock()


def refresh_lock() -> None:
    cmd = ["uv", "lock"]
    interpreter = os.environ.get("UV_PYTHON") or _available_python()
    if interpreter:
        cmd.extend(["--python", interpreter])
    subprocess.run(cmd, cwd=ROOT, check=True)


def _available_python() -> str | None:
    for candidate in (sys.executable, "python3", "python"):
        if not candidate:
            continue
        try:
            result = subprocess.run(
                [candidate, "-c", "import sys; print(sys.version.split()[0])"],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            continue
        if result.returncode == 0 and result.stdout.strip():
            return candidate
    return None


def changelog_entry(version: str) -> str:
    return (
        f"## {version}\n\n"
        "Describe this release.\n\n"
        f"See [`release-notes/v{version}.md`](release-notes/v{version}.md).\n\n"
    )


def update_changelog(version: str) -> None:
    path = ROOT / "CHANGELOG.md"
    text = path.read_text(encoding="utf-8")
    if f"\n## {version}\n" in f"\n{text}" or text.startswith(f"## {version}\n"):
        return
    marker = "\n## "
    if marker not in text:
        raise SystemExit("could not find a release heading in CHANGELOG.md")
    index = text.index(marker) + 1
    text = text[:index] + changelog_entry(version) + text[index:]
    path.write_text(text, encoding="utf-8")


def release_note(version: str) -> None:
    path = ROOT / "release-notes" / f"v{version}.md"
    if path.exists():
        return
    path.write_text(
        f"# {version}\n\nDescribe this release.\n",
        encoding="utf-8",
    )


def update_book_index(path: Path, version: str) -> None:
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    if f"Current release is {version}." in text:
        return

    text = re.sub(
        r"(?m)^since: .*$",
        f"since: {version}",
        text,
        count=1,
    )
    text = re.sub(
        r"(?m)^  summary: Current release is .*$",
        f"  summary: Current release is {version}.",
        text,
        count=1,
    )

    if f"\n## {version}\n" not in text:
        section = (
            f"\n## {version}\n\n"
            "Describe this release.\n\n"
            f"See the full note in `release-notes/v{version}.md` at the repository root.\n"
        )
        marker = "\n## "
        if marker in text:
            index = text.index(marker)
            text = text[:index] + section + text[index:]
        else:
            if not text.endswith("\n"):
                text += "\n"
            text += section

    text = re.sub(
        r"(?m)^The daemon runs new migrations at startup when a release includes them\. "
        r"Restart a user service\n.*$",
        "The daemon runs new migrations at startup when a release includes them. "
        "Restart a user service\nafter upgrading. No new config is required unless noted "
        "in the release note.",
        text,
    )
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bump downcroc version and scaffold release files."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("version", nargs="?", help="explicit version, e.g. 1.3.2")
    group.add_argument(
        "--bump",
        choices=[
            "major",
            "minor",
            "patch",
            "stable",
            "alpha",
            "beta",
            "rc",
            "post",
            "dev",
        ],
    )
    parser.add_argument(
        "--frozen",
        action="store_true",
        help="set the version without refreshing uv.lock (not recommended)",
    )
    args = parser.parse_args()

    if args.bump:
        cmd = ["uv", "version", "--bump", args.bump, "--short", "--frozen"]
        version = run(*cmd)
        if not args.frozen:
            refresh_lock()
    else:
        version = args.version
        assert version is not None
        set_version(version, frozen=args.frozen)

    update_changelog(version)
    release_note(version)
    for index in BOOK_INDEXES:
        update_book_index(index, version)
    print(version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
