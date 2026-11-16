#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
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


def set_version(version: str, *, frozen: bool = True) -> None:
    cmd = ["uv", "version", version]
    if frozen:
        cmd.append("--frozen")
    subprocess.run(cmd, cwd=ROOT, check=True)


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
    group.add_argument("--bump", choices=["major", "minor", "patch"])
    parser.add_argument(
        "--sync",
        action="store_true",
        help="allow uv to sync/lock (default: --frozen)",
    )
    args = parser.parse_args()

    frozen = not args.sync
    if args.bump:
        cmd = ["uv", "version", "--bump", args.bump, "--short"]
        if frozen:
            cmd.append("--frozen")
        version = run(*cmd)
    else:
        version = args.version
        assert version is not None
        set_version(version, frozen=frozen)

    update_changelog(version)
    release_note(version)
    for index in BOOK_INDEXES:
        update_book_index(index, version)
    print(version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
