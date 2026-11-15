"""Check book coverage and map source changes to affected pages.

This is the drift guard described in plan/17-three-part-book.md. It ties the
parser tree, page frontmatter, glossary, and captured screens together.

Usage:
    uv run python scripts/docs_map.py check
    uv run python scripts/docs_map.py touched <source> [<source>...]
    uv run python scripts/docs_map.py diff [<rev>]
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from downcroc.cli.parser import build_parser
from downcroc.cli.ui.tree.spec import GLOBAL_DESTS, CommandSpec, build_tree

REPO = Path(__file__).resolve().parents[1]
DOCS_ROOT = REPO / "src/downcroc/docs"
SCREENS_DIR = DOCS_ROOT / "assets/screens"
GLOSSARY_DIR = DOCS_ROOT / "part-iii/glossary"
TERM_REF = re.compile(r"\[\[([a-z0-9][a-z0-9_-]*)\]\]")
POINTER_RE = re.compile(r"^\s*⤷.*?([A-Za-z0-9_./-]+\.md(?:#[A-Za-z0-9_-]+)?)\s*$")
FLAG_TOKEN = re.compile(r"(?<!\w)--[a-z0-9][a-z0-9-]*")


@dataclass
class Page:
    path: Path
    front: dict[str, object]
    body: str
    commands: set[str] = field(default_factory=set)
    flags: set[str] = field(default_factory=set)
    screens: set[str] = field(default_factory=set)
    concepts: set[str] = field(default_factory=set)

    @property
    def rel(self) -> str:
        return str(self.path.relative_to(REPO))

    @property
    def is_part_i(self) -> bool:
        return "/part-i/" in self.rel.replace("\\", "/")


def parse_frontmatter(text: str) -> tuple[dict[str, object], str]:
    if not text.startswith("---\n"):
        return {}, text
    try:
        _, rest = text.split("---\n", 1)
        head, body = rest.split("\n---\n", 1)
    except ValueError:
        return {}, text
    data: dict[str, object] = {}
    for line in head.splitlines():
        if not line.strip() or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            if not inner:
                data[key] = []
            else:
                data[key] = [
                    item.strip().strip("\"'")
                    for item in inner.split(",")
                    if item.strip()
                ]
        else:
            data[key] = value.strip("\"'")
    return data, body


def load_pages() -> list[Page]:
    pages: list[Page] = []
    for path in sorted(DOCS_ROOT.rglob("*.md")):
        rel = str(path.relative_to(DOCS_ROOT)).replace("\\", "/")
        if rel.startswith("part-iii/glossary/"):
            continue
        if path.name == "37-glossary.md":
            continue
        text = path.read_text(encoding="utf-8")
        front, body = parse_frontmatter(text)
        page = Page(path=path, front=front, body=body)
        for item in front.get("commands") or []:
            page.commands.add(str(item))
        for item in front.get("flags") or []:
            page.flags.add(str(item))
        for item in front.get("screens") or []:
            page.screens.add(str(item))
        for item in front.get("concepts") or []:
            page.concepts.add(str(item))
        pages.append(page)
    return pages


def command_id(path: tuple[str, ...]) -> str:
    return ".".join(path)


def iter_commands(node: CommandSpec):
    if node.path:
        yield node
    for child in node.children:
        yield from iter_commands(child)


def tree_inventory() -> tuple[set[str], dict[str, set[str]]]:
    tree = build_tree(build_parser())
    commands: set[str] = set()
    flags: dict[str, set[str]] = {}
    for spec in iter_commands(tree.root):
        cid = command_id(spec.path)
        commands.add(cid)
        fset: set[str] = set()
        for arg in (*spec.positionals, *spec.options):
            if arg.global_option or arg.dest in GLOBAL_DESTS:
                continue
            if arg.flags:
                fset.add(arg.flags[0])
            else:
                fset.add(arg.dest)
        flags[cid] = fset
    return commands, flags


def declared_stubs() -> set[str]:
    stubs = set()
    part_ii = DOCS_ROOT / "part-ii"
    if part_ii.is_dir():
        for path in part_ii.rglob("*.md"):
            stubs.add(path.name)
    stub_file = part_ii / "_stubs.txt"
    if stub_file.is_file():
        for line in stub_file.read_text(encoding="utf-8").splitlines():
            name = line.strip()
            if name and not name.startswith("#"):
                stubs.add(Path(name).name)
    return stubs


def glossary_slugs() -> set[str]:
    if not GLOSSARY_DIR.is_dir():
        return set()
    return {path.stem for path in GLOSSARY_DIR.glob("*.md")}


def check_coverage(pages: list[Page]) -> list[str]:
    errors: list[str] = []
    all_commands, all_flags = tree_inventory()
    claimed_commands: set[str] = set()
    claimed_flags: set[tuple[str, str]] = set()
    for page in pages:
        for cmd in page.commands:
            if cmd not in all_commands:
                errors.append(f"stale command in {page.rel}: {cmd}")
            else:
                claimed_commands.add(cmd)
        for flag in page.flags:
            # accept "cmd.path --flag" or bare "--flag"
            if " " in flag:
                cmd, fname = flag.rsplit(" ", 1)
                if cmd not in all_flags or fname not in all_flags.get(cmd, set()):
                    errors.append(f"stale flag in {page.rel}: {flag}")
                else:
                    claimed_flags.add((cmd, fname))
            else:
                matches = [
                    c
                    for c, fs in all_flags.items()
                    if flag in fs and c in page.commands
                ]
                if not matches:
                    errors.append(f"stale/unscoped flag in {page.rel}: {flag}")
                else:
                    for cmd in matches:
                        claimed_flags.add((cmd, flag))
    part_ii_stub = declared_stubs()
    # commands/flags must be claimed by a page or have a Part II stub naming them
    for cmd in sorted(all_commands - claimed_commands):
        # allow if a part-ii stub/chapter claims the root area (best-effort)
        stub_names = {f"{cmd.replace('.', '-')}.md", f"{cmd.split('.')[0]}.md"}
        if not (stub_names & part_ii_stub):
            errors.append(f"unclaimed command: {cmd}")
    for cmd, fs in all_flags.items():
        for flag in sorted(fs):
            if (cmd, flag) not in claimed_flags:
                stub_names = {f"{cmd.replace('.', '-')}.md", f"{cmd.split('.')[0]}.md"}
                if not (stub_names & part_ii_stub):
                    errors.append(f"unclaimed flag: {cmd} {flag}")
    return errors


def check_pointers(pages: list[Page]) -> list[str]:
    errors: list[str] = []
    stubs = declared_stubs()
    for page in pages:
        for line in page.body.splitlines():
            match = POINTER_RE.match(line)
            if not match:
                continue
            raw = match.group(1)
            target = raw.split("#", 1)[0]
            resolved = (page.path.parent / target).resolve()
            if resolved.is_file():
                continue
            name = Path(target).name
            if name in stubs:
                continue
            # Part II slots are declared by plan/17 and may not be written yet.
            if "part-ii" in target.replace("\\", "/"):
                continue
            errors.append(f"broken pointer in {page.rel}: {target}")
    return errors


def check_terms(pages: list[Page]) -> list[str]:
    errors: list[str] = []
    slugs = glossary_slugs()
    for page in pages:
        for match in TERM_REF.finditer(page.body):
            term = match.group(1)
            if term not in slugs:
                errors.append(f"unknown term [[{term}]] in {page.rel}")
    return errors


def check_screens(pages: list[Page]) -> list[str]:
    errors: list[str] = []
    for page in pages:
        for screen in page.screens:
            if not (SCREENS_DIR / f"{screen}.txt").is_file():
                errors.append(f"missing screen in {page.rel}: {screen}")
    return errors


def check_part_i_caps(pages: list[Page]) -> list[str]:
    errors: list[str] = []
    for page in pages:
        if not page.is_part_i:
            continue
        # flags shown in prose: count distinct --flags outside frontmatter in body
        shown = set(FLAG_TOKEN.findall(page.body))
        if len(shown) > 3:
            errors.append(f"part I flag cap exceeded in {page.rel}: {sorted(shown)}")
        # error-code tables: markdown table rows that look like code identifiers in col 1
        lines = page.body.splitlines()
        for i, line in enumerate(lines):
            if not line.strip().startswith("|"):
                continue
            # header/separator heuristics
            header = line.lower()
            if "code" in header and "meaning" in header or "reason" in header:
                # count following data rows until table ends
                rows = 0
                for row in lines[i + 1 :]:
                    stripped = row.strip()
                    if not stripped.startswith("|"):
                        break
                    if set(stripped.replace("|", "").strip()) <= {"-", ":"}:
                        continue
                    rows += 1
                if rows > 0:
                    errors.append(f"part I error-code table in {page.rel}")
                break
    return errors


def run_check() -> int:
    pages = load_pages()
    problems: list[str] = []
    problems.extend(check_coverage(pages))
    problems.extend(check_pointers(pages))
    problems.extend(check_terms(pages))
    problems.extend(check_screens(pages))
    problems.extend(check_part_i_caps(pages))
    # also run glossary self-check (drift + see_also + term refs)
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "glossary", REPO / "scripts/glossary.py"
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("could not load glossary.py")
        glossary_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(glossary_mod)
        entries = glossary_mod.load_entries()
        rendered = glossary_mod.render(entries)
        current = (
            glossary_mod.ARTIFACT.read_text(encoding="utf-8")
            if glossary_mod.ARTIFACT.exists()
            else ""
        )
        slugs = {e.slug for e in entries}
        refs = glossary_mod.collect_refs()
        for term in refs:
            if term not in slugs:
                problems.append(f"glossary: unknown [[{term}]] reference")
        for entry in entries:
            for target in entry.see_also:
                if target not in slugs:
                    problems.append(f"glossary: bad see_also {entry.slug}->{target}")
        if current != rendered:
            problems.append("glossary artifact is out of date")
    except Exception as error:  # noqa: BLE001
        problems.append(f"glossary check failed: {error}")

    if problems:
        for item in problems:
            print(item, file=sys.stderr)
        return 1
    print(f"ok: {len(pages)} pages checked")
    return 0


def commands_for_source(path: str) -> set[str]:
    p = Path(path)
    parts = p.parts
    cmds: set[str] = set()
    name = p.stem
    if "cli/commands" in path.replace("\\", "/"):
        cmds.add(name)
        # common mappings
        aliases = {
            "state": "status",
            "sending": "sending",
            "jobs": "job",
            "accounts": "account",
            "batches": "batch",
            "providers": "provider",
            "templates": "template",
            "failed": "failed",
            "logs": "logs",
            "stats": "stats",
        }
        cmds.add(aliases.get(name, name))
    if "cli/parser" in path.replace("\\", "/"):
        cmds.add(name)
        aliases = {"batch": "batch", "jobs": "job", "accounts": "account"}
        cmds.add(aliases.get(name, name))
    if "cli/ui/tree" in path.replace("\\", "/"):
        cmds.add("*")
    # domain/core hints
    for token, cmd in (
        ("dispatch", "sending"),
        ("outbound", "sending"),
        ("job", "job"),
        ("batch", "batch"),
        ("account", "account"),
        ("fail", "failed"),
        ("followup", "batch"),
        ("vault", "vault"),
        ("log", "logs"),
        ("stat", "stats"),
    ):
        if token in name or any(token in part for part in parts):
            cmds.add(cmd)
    return cmds


def pages_for_commands(pages: list[Page], wanted: set[str]) -> list[Page]:
    if "*" in wanted:
        return pages
    out = []
    roots = {w.split(".")[0] for w in wanted}
    for page in pages:
        if page.commands & wanted:
            out.append(page)
            continue
        page_roots = {c.split(".")[0] for c in page.commands}
        if page_roots & roots:
            out.append(page)
    return out


def run_touched(sources: list[str]) -> int:
    pages = load_pages()
    wanted: set[str] = set()
    for source in sources:
        wanted |= commands_for_source(source)
    affected = pages_for_commands(pages, wanted)
    for source in sources:
        cmds = sorted(commands_for_source(source))
        print(f"{source}: {', '.join(cmds) if cmds else '(no mapped commands)'}")
    if affected:
        print("pages:")
        for page in affected:
            print(f"  - {page.rel}")
    else:
        print("pages: (none matched)")
    return 0


def run_diff(rev: str) -> int:
    result = subprocess.run(
        ["git", "diff", "--name-only", rev],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(result.stderr.strip() or "git diff failed", file=sys.stderr)
        return result.returncode or 1
    sources = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not sources:
        print("no changed files")
        return 0
    return run_touched(sources)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check")
    touched = sub.add_parser("touched")
    touched.add_argument("sources", nargs="+")
    diff = sub.add_parser("diff")
    diff.add_argument("rev", nargs="?", default="HEAD~1")
    args = parser.parse_args()
    if args.command == "check":
        return run_check()
    if args.command == "touched":
        return run_touched(args.sources)
    return run_diff(args.rev)


if __name__ == "__main__":
    sys.exit(main())
