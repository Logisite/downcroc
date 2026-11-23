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

    @property
    def is_holder(self) -> bool:
        status = str(self.front.get("status") or "").strip().lower()
        if status in {"stub", "holder", "placeholder", "todo", "wip"}:
            return True
        holder = self.front.get("holder")
        if isinstance(holder, bool):
            return holder
        return str(holder).strip().lower() in {"true", "yes", "1"}


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


def parse_stub_file() -> tuple[set[str], dict[str, str]]:
    """Return (declared names/paths, alias basename -> canonical rel path)."""
    declared: set[str] = set()
    aliases: dict[str, str] = {}
    part_ii = DOCS_ROOT / "part-ii"
    if part_ii.is_dir():
        for path in part_ii.rglob("*.md"):
            rel = str(path.relative_to(part_ii)).replace("\\", "/")
            declared.add(path.name)
            declared.add(rel)
    stub_file = part_ii / "_stubs.txt"
    if stub_file.is_file():
        for raw in stub_file.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "->" in line:
                left, right = line.split("->", 1)
                alias = left.strip()
                target = right.strip().replace("\\", "/")
                aliases[Path(alias).name] = target
                declared.add(Path(alias).name)
                declared.add(target)
                declared.add(Path(target).name)
            else:
                token = line.replace("\\", "/")
                declared.add(Path(token).name)
                declared.add(token)
    return declared, aliases


def declared_stubs() -> set[str]:
    declared, _aliases = parse_stub_file()
    return declared


def stub_aliases() -> dict[str, str]:
    _declared, aliases = parse_stub_file()
    return aliases


def glossary_slugs() -> set[str]:
    if not GLOSSARY_DIR.is_dir():
        return set()
    slugs: set[str] = set()
    paths = list(GLOSSARY_DIR.glob("_*.md")) or list(GLOSSARY_DIR.glob("*.md"))
    for path in paths:
        slugs.add(path.stem.removeprefix("_"))
    return slugs


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
    aliases = stub_aliases()
    part_ii = DOCS_ROOT / "part-ii"
    pointer_target = re.compile(r"([A-Za-z0-9_./-]+\.md(?:#[A-Za-z0-9_-]+)?)")
    for page in pages:
        lines = page.body.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            target = None
            if line.lstrip().startswith("⤷"):
                match = POINTER_RE.match(line)
                if match:
                    target = match.group(1)
                elif i + 1 < len(lines):
                    nxt = pointer_target.search(lines[i + 1])
                    if nxt:
                        target = nxt.group(1)
            if target is None:
                i += 1
                continue
            raw = target.split("#", 1)[0].replace("\\", "/")
            resolved = (page.path.parent / raw).resolve()
            name = Path(raw).name
            alias_target = aliases.get(name)
            alias_resolved = (
                (part_ii / alias_target).resolve() if alias_target else None
            )
            if not (
                resolved.is_file()
                or name in stubs
                or raw in stubs
                or (alias_resolved and alias_resolved.is_file())
                or "part-ii" in raw
            ):
                errors.append(f"broken pointer in {page.rel}: {raw}")
            i += 1
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


LOG_EVENT_CALL = re.compile(
    r'\.(?:debug|info|warning|warn|error|critical)\(\s*"([a-zA-Z0-9_.-]+)"'
)
DOC_EVENT_ITEM = re.compile(r"^- `([a-z0-9_.-]+)` \(\*\*", re.MULTILINE)
CAPABILITY_HEADING = re.compile(r"^###\s+(.+)$", re.MULTILINE)
CAPABILITY_DOC = DOCS_ROOT / "part-ii/28-extension/capabilities.md"


def _read_event_list(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    items: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        items.add(line)
    return items


def emitted_log_events() -> set[str]:
    events: set[str] = set()
    src = REPO / "src/downcroc"
    if not src.is_dir():
        return events
    for path in src.rglob("*.py"):
        try:
            text_py = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for match in LOG_EVENT_CALL.finditer(text_py):
            events.add(match.group(1))
    return events


def documented_log_events() -> set[str]:
    events: set[str] = set()
    events_dir = DOCS_ROOT / "part-ii/19-logs/events"
    if not events_dir.is_dir():
        return events
    for path in events_dir.glob("*.md"):
        if path.name == "index.md":
            continue
        try:
            text_md = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for match in DOC_EVENT_ITEM.finditer(text_md):
            events.add(match.group(1))
    return events


def check_log_events() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    events_dir = DOCS_ROOT / "part-ii/19-logs/events"
    undocumented_allow = _read_event_list(events_dir / "_undocumented_log_events.txt")
    orphan_allow = _read_event_list(events_dir / "_orphan_documented_log_events.txt")
    emitted = emitted_log_events()
    documented = documented_log_events()
    undocumented = sorted(emitted - documented - undocumented_allow)
    orphans = sorted(documented - emitted - orphan_allow)
    for name in undocumented:
        errors.append(f"undocumented log event: {name}")
    for name in orphans:
        errors.append(f"orphaned documented log event: {name}")
    active_undoc = sorted((emitted - documented) & undocumented_allow)
    active_orphan = sorted((documented - emitted) & orphan_allow)
    if active_undoc:
        warnings.append(
            f"override: {len(active_undoc)} emitted log event(s) allowed undocumented via 19-logs/events/_undocumented_log_events.txt"
        )
    if active_orphan:
        warnings.append(
            f"override: {len(active_orphan)} documented log event(s) allowed orphaned via 19-logs/events/_orphan_documented_log_events.txt"
        )
    return errors, warnings


def check_config_reference() -> list[str]:
    errors: list[str] = []
    ref = DOCS_ROOT / "part-iii/38-config.md"
    if not ref.is_file():
        return ["missing config reference: part-iii/38-config.md"]
    text = ref.read_text(encoding="utf-8")
    try:
        from downcroc.runtime.config.spec import describe

        fields = describe()
    except Exception as error:  # noqa: BLE001
        return [f"config reference check failed: {error}"]
    for item in fields:
        path = str(item.get("path") or "")
        if not path:
            continue
        if f"`{path}`" not in text:
            errors.append(f"undocumented config field in part-iii/38-config.md: {path}")
    return errors


def check_extension_capabilities() -> list[str]:
    if not CAPABILITY_DOC.is_file():
        return ["missing capability reference: part-ii/28-extension/capabilities.md"]
    text = CAPABILITY_DOC.read_text(encoding="utf-8")
    from downcroc.extensions.broker import Broker
    from downcroc.extensions.capabilities import register_capabilities

    broker = Broker(None, None, None, None)
    register_capabilities(broker)
    registered = set(broker.capabilities)
    documented: set[str] = set()
    for match in CAPABILITY_HEADING.finditer(text):
        for piece in re.split(r",|\band\b", match.group(1)):
            token = piece.strip().strip("`")
            if token in registered:
                documented.add(token)
    errors = [
        f"undocumented extension capability in part-ii/28-extension/capabilities.md: {name}"
        for name in sorted(registered - documented)
    ]
    errors.extend(
        f"stale extension capability in part-ii/28-extension/capabilities.md: {name}"
        for name in sorted(documented - registered)
    )
    return errors


def holder_pages(pages: list[Page]) -> list[Page]:
    return [page for page in pages if page.is_holder]


def report_holders(pages: list[Page]) -> None:
    holders = holder_pages(pages)
    if not holders:
        return
    for page in holders:
        title = str(page.front.get("title") or page.path.stem)
        print(f"holder: {page.rel} - {title}", file=sys.stderr)


def run_holders() -> int:
    pages = load_pages()
    holders = holder_pages(pages)
    if not holders:
        print("no holder pages")
        return 0
    for page in holders:
        title = str(page.front.get("title") or page.path.stem)
        print(f"{page.rel}\t{title}")
    print(f"{len(holders)} holder page(s)", file=sys.stderr)
    return 0


def run_check() -> int:
    pages = load_pages()
    report_holders(pages)
    problems: list[str] = []
    problems.extend(check_coverage(pages))
    problems.extend(check_pointers(pages))
    problems.extend(check_terms(pages))
    problems.extend(check_screens(pages))
    problems.extend(check_part_i_caps(pages))
    log_errors, log_warnings = check_log_events()
    problems.extend(log_errors)
    for item in log_warnings:
        print(item, file=sys.stderr)
    problems.extend(check_config_reference())
    problems.extend(check_extension_capabilities())
    # also run glossary self-check (drift + see_also + term refs)
    try:
        import importlib.util

        glossary_path = REPO / "scripts/glossary.py"
        sys.path.insert(0, str(REPO / "scripts"))
        try:
            spec = importlib.util.spec_from_file_location(
                "downcroc_glossary_check", glossary_path
            )
            if spec and spec.loader:
                glossary_mod = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = glossary_mod
                spec.loader.exec_module(glossary_mod)
            else:
                import glossary as glossary_mod  # type: ignore[assignment]
        finally:
            try:
                sys.path.remove(str(REPO / "scripts"))
            except ValueError:
                pass
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
    stub_file = DOCS_ROOT / "part-ii/_stubs.txt"
    if stub_file.is_file():
        aliases = 0
        for raw in stub_file.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "->" in line:
                aliases += 1
        if aliases:
            print(
                f"note: {aliases} legacy Part II alias(es) defined in part-ii/_stubs.txt",
                file=sys.stderr,
            )
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
    sub.add_parser("holders")
    touched = sub.add_parser("touched")
    touched.add_argument("sources", nargs="+")
    diff = sub.add_parser("diff")
    diff.add_argument("rev", nargs="?", default="HEAD~1")
    args = parser.parse_args()
    if args.command == "check":
        return run_check()
    if args.command == "holders":
        return run_holders()
    if args.command == "touched":
        return run_touched(args.sources)
    return run_diff(args.rev)


if __name__ == "__main__":
    sys.exit(main())
