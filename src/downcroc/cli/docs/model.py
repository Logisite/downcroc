from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

HEADING = re.compile(r"^(#{1,3})\s+(.+?)\s*$")
FENCE = re.compile(r"^```([A-Za-z0-9_+-]*)\s*$")
ADMONITION = re.compile(r'^!!!\s+([a-z]+)(?:\s+"([^"]*)")?\s*$')
IMAGE = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$")


@dataclass(frozen=True)
class Block:
    kind: str
    text: str
    language: str = ""
    title: str = ""
    tone: str = "note"


@dataclass
class Page:
    path: Path
    rel: str
    title: str
    description: str
    body: str
    tags: tuple[str, ...] = ()
    audience: str = "user"
    status: str = "stable"
    since: str | None = None
    order: int = 0
    summary: str = ""
    max_width: int = 100
    toc: bool = True
    search_boost: float = 1.0
    headings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def slug(self) -> str:
        return self.rel.removesuffix(".md").replace("/", "-")

    @property
    def raw(self) -> str:
        return self.path.read_text(encoding="utf-8")


def load_pages(root: Path) -> list[Page]:
    pages = []
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        meta, body = frontmatter(text)
        pages.append(
            Page(
                path=path,
                rel=rel,
                title=str(meta.get("title") or _first_heading(body) or rel),
                description=str(meta.get("description") or ""),
                body=body,
                tags=_tuple(meta.get("tags")),
                audience=str(meta.get("audience") or "user"),
                status=str(meta.get("status") or "stable"),
                since=str(meta["since"]) if meta.get("since") else None,
                order=int(meta.get("order") or 0),
                summary=str(meta.get("terminal_summary") or ""),
                max_width=int(meta.get("terminal_max_width") or 100),
                toc=bool(meta.get("terminal_toc", True)),
                search_boost=float(meta.get("search_boost") or 1.0),
                headings=headings(body),
            )
        )
    return pages


def frontmatter(text: str) -> tuple[dict[str, object], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    raw = text[4:end]
    meta: dict[str, object] = {}
    current = ""
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("  ") and current:
            key, _, value = line.strip().partition(":")
            meta[f"{current}_{key.strip()}"] = _value(value)
            continue
        key, _, value = line.partition(":")
        current = key.strip()
        meta[current] = _value(value)
    return meta, text[end + 5 :]


def _value(raw: str) -> object:
    value = raw.strip()
    if value.startswith("[") and value.endswith("]"):
        return tuple(
            item.strip().strip('"').strip("'")
            for item in value[1:-1].split(",")
            if item.strip()
        )
    return value.strip('"').strip("'")


def _tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, tuple):
        return tuple(str(item) for item in value)
    if isinstance(value, str) and value:
        return (value,)
    return ()


def _first_heading(body: str) -> str:
    for line in body.splitlines():
        found = HEADING.match(line)
        if found:
            return found.group(2)
    return ""


def headings(body: str) -> tuple[str, ...]:
    found: list[str] = []
    fenced = False
    for line in body.splitlines():
        if FENCE.match(line):
            fenced = not fenced
            continue
        if fenced:
            continue
        match = HEADING.match(line)
        if match:
            found.append(match.group(2))
    return tuple(found)


def blocks(body: str) -> list[Block]:
    result: list[Block] = []
    lines = body.splitlines()
    index = 0
    prose: list[str] = []

    def flush() -> None:
        if prose:
            text = "\n".join(prose).strip()
            if text:
                result.append(Block("markdown", text))
            prose.clear()

    while index < len(lines):
        line = lines[index]
        fence = FENCE.match(line)
        if fence:
            flush()
            language = fence.group(1)
            code: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].startswith("```"):
                code.append(lines[index])
                index += 1
            index += 1
            kind = "mermaid" if language == "mermaid" else "code"
            result.append(Block(kind, "\n".join(code), language=language))
            continue
        admonition = ADMONITION.match(line)
        if admonition:
            flush()
            tone = admonition.group(1) or "note"
            title = admonition.group(2) or tone.title()
            body_lines: list[str] = []
            index += 1
            while index < len(lines) and (
                not lines[index].strip() or lines[index].startswith("    ")
            ):
                body_lines.append(
                    lines[index][4:] if lines[index].startswith("    ") else ""
                )
                index += 1
            result.append(
                Block("callout", "\n".join(body_lines).strip(), title=title, tone=tone)
            )
            continue
        image = IMAGE.match(line.strip())
        if image:
            flush()
            result.append(Block("image", image.group(1), title=image.group(2)))
            index += 1
            continue
        if line.strip().startswith("|") and _table_end(lines, index):
            flush()
            table: list[str] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                table.append(lines[index])
                index += 1
            result.append(Block("table", "\n".join(table)))
            continue
        prose.append(line)
        index += 1
    flush()
    return result


def _table_end(lines: list[str], index: int) -> bool:
    return index + 1 < len(lines) and set(lines[index + 1].strip()) <= {
        "|",
        "-",
        ":",
        " ",
    }


def table_rows(text: str) -> tuple[list[str], list[list[str]]]:
    rows = []
    for line in text.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        rows.append(cells)
    if len(rows) >= 2 and set("".join(rows[1])) <= {"-", ":", " "}:
        return rows[0], rows[2:]
    return rows[0] if rows else [], rows[1:]
