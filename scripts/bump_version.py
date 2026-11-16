#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def set_version(version: str, *, frozen: bool = True) -> None:
    cmd = ["uv", "version", version]
    if frozen:
        cmd.append("--frozen")
    run(*cmd)


def changelog_entry(version: str) -> str:
    return (
        f"## {version}\n\n"
        "Describe this release.\n\n"
        f"See [`release-notes/v{version}.md`](release-notes/v{version}.md).\n\n"
    )


def update_changelog(version: str) -> None:
    path = ROOT / "CHANGELOG.md"
    text = path.read_text(encoding="utf-8")
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bump downcroc version and scaffold release files."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("version", nargs="?", help="explicit version, e.g. 1.3.2")
    group.add_argument("--bump", choices=["major", "minor", "patch"])
    parser.add_argument(
        "--sync", action="store_true", help="allow uv to sync/lock (default: --frozen)"
    )
    args = parser.parse_args()

    frozen = not args.sync
    if args.bump:
        cmd = ["uv", "version", "--bump", args.bump, "--short"]
        if frozen:
            cmd.append("--frozen")
        version = subprocess.check_output(cmd, cwd=ROOT, text=True).strip()
    else:
        version = args.version
        set_version(version, frozen=frozen)

    update_changelog(version)
    release_note(version)
    print(version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
