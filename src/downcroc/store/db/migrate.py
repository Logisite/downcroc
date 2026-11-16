from __future__ import annotations

import time
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, inspect

from downcroc.domain.errors_base import DomainError
from downcroc.runtime.logging.setup import EventLogger

MIGRATIONS = Path(__file__).resolve().parent / "migrations"


class MigrationFailed(DomainError):
    code = "db_migration_failed"
    status = 500


def alembic_config() -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    return config


def script_directory() -> ScriptDirectory:
    return ScriptDirectory.from_config(alembic_config())


def current_head() -> str | None:
    return script_directory().get_current_head()


def known_revisions() -> set[str]:
    return {script.revision for script in script_directory().walk_revisions()}


def current_revision(engine: Engine) -> str | None:
    with engine.connect() as connection:
        if not inspect(connection).has_table("alembic_version"):
            return None
        return MigrationContext.configure(connection).get_current_revision()


def check_revisions(engine: Engine, log: EventLogger) -> None:
    """Validate the recorded revision before startup touches the database.

    Emits one short structured event rather than letting alembic dump a
    traceback through the ASGI lifespan into the daemon log.
    """
    current = current_revision(engine)
    head = current_head()
    revisions = known_revisions()
    if current is not None and current not in revisions:
        message = f"database revision {current} is not in this build of downcroc"
        hint = (
            "install a newer downcroc release whose migrations include "
            f"{current}, or restore a backup made with the matching version; "
            "do not run an older release against this database"
        )
        log.error(
            "db.migrate_failed",
            reason="unknown_revision",
            current=current,
            head=head or "none",
            known_revisions=sorted(revisions),
            hint=hint,
        )
        raise MigrationFailed(message, hint=hint)
    log.info(
        "db.revision_ok",
        current=current or "none",
        head=head or "none",
        known_revisions=len(revisions),
    )


def run_migrations(engine: Engine, log: EventLogger) -> None:
    config = alembic_config()
    config.attributes["url"] = engine.url
    check_revisions(engine, log)
    current = current_revision(engine)
    head = current_head()
    started = time.monotonic()
    try:
        command.upgrade(config, "head")
    except Exception as error:
        hint = (
            "check the database is not in use by another daemon, then retry; "
            "if it persists, restore a backup or report the error code"
        )
        log.error(
            "db.migrate_failed",
            reason="upgrade_failed",
            current=current or "none",
            head=head or "none",
            error=type(error).__name__,
            detail=str(error)[:300],
            hint=hint,
        )
        raise MigrationFailed(
            f"database migration failed: {type(error).__name__}: {str(error)[:200]}",
            hint=hint,
        ) from error
    log.info(
        "db.migrate",
        **{
            "from": current or "none",
            "to": head or "none",
            "duration_ms": round((time.monotonic() - started) * 1000),
        },
    )
