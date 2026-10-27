from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from downcroc.runtime.fs import restrict

TABLES = ("accounts", "batches", "jobs", "messages", "threads")
CONTENT_REFS = (
    ("batches", "source_ref"),
    ("jobs", "body_ref"),
    ("attachments", "path"),
)


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(path), timeout=10)
    connection.execute("PRAGMA busy_timeout = 10000")
    return connection


def _table_names(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    return {str(row[0]) for row in rows}


def snapshot_database(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.unlink(missing_ok=True)
    with closing(_connect(source)) as reader, closing(_connect(target)) as writer:
        reader.backup(writer)
        writer.commit()
    restrict(target, 0o600)


def schema_revision(path: Path) -> str | None:
    with closing(_connect(path)) as connection:
        if "alembic_version" not in _table_names(connection):
            return None
        row = connection.execute(
            "SELECT version_num FROM alembic_version LIMIT 1"
        ).fetchone()
    return str(row[0]) if row and row[0] else None


def table_counts(path: Path) -> dict[str, int]:
    found: dict[str, int] = {}
    with closing(_connect(path)) as connection:
        names = _table_names(connection)
        for table in TABLES:
            if table not in names:
                found[table] = 0
                continue
            row = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            found[table] = int(row[0]) if row else 0
    return found


def integrity_problems(path: Path) -> list[str]:
    with closing(_connect(path)) as connection:
        rows = connection.execute("PRAGMA integrity_check").fetchall()
    return [str(row[0]) for row in rows if str(row[0]) != "ok"]


def foreign_key_problems(path: Path) -> list[str]:
    with closing(_connect(path)) as connection:
        rows = connection.execute("PRAGMA foreign_key_check").fetchall()
    return [":".join(str(part) for part in row) for row in rows]


def content_refs(path: Path) -> set[str]:
    refs: set[str] = set()
    with closing(_connect(path)) as connection:
        names = _table_names(connection)
        for table, column in CONTENT_REFS:
            if table not in names:
                continue
            rows = connection.execute(
                f"SELECT {column} FROM {table} WHERE {column} IS NOT NULL"
            )
            refs.update(str(row[0]) for row in rows if row[0])
    return refs


def missing_content(path: Path, root: Path) -> list[str]:
    return sorted(ref for ref in content_refs(path) if not (root / ref).is_file())


def count_mismatches(
    expected: dict[str, int],
    actual: dict[str, int],
) -> list[str]:
    return [table for table, count in expected.items() if actual.get(table) != count]
