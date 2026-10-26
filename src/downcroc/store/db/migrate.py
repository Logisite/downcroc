from __future__ import annotations

import time
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, inspect

from downcroc.runtime.logging.setup import EventLogger

ALEMBIC_INI = "alembic.ini"
MIGRATIONS = "migrations"


def project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / ALEMBIC_INI).is_file() and (parent / MIGRATIONS).is_dir():
            return parent
    raise RuntimeError(f"cannot find {ALEMBIC_INI} above {__file__}")


def alembic_config() -> Config:
    root = project_root()
    config = Config(str(root / ALEMBIC_INI))
    config.set_main_option("script_location", str(root / MIGRATIONS))
    return config


def script_directory() -> ScriptDirectory:
    return ScriptDirectory.from_config(alembic_config())


def current_head() -> str | None:
    return script_directory().get_current_head()


def known_revisions() -> set[str]:
    return {script.revision for script in script_directory().walk_revisions()}


def run_migrations(engine: Engine, log: EventLogger) -> None:
    config = alembic_config()
    config.attributes["url"] = engine.url

    with engine.connect() as connection:
        current = None
        if inspect(connection).has_table("alembic_version"):
            current = MigrationContext.configure(connection).get_current_revision()

    head = ScriptDirectory.from_config(config).get_current_head()
    started = time.monotonic()
    command.upgrade(config, "head")
    log.info(
        "db.migrate",
        **{
            "from": current or "none",
            "to": head or "none",
            "duration_ms": round((time.monotonic() - started) * 1000),
        },
    )
