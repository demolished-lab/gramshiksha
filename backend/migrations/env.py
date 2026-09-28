"""Alembic environment for GramShiksha.

The database URL is read from ``app.config`` — the *same* object the server
uses — so a migration can never be pointed at a different database than the
app. Importing ``app.config`` opens no connection, so this file is safe to run
offline too.

Layout note: the migration scripts live in ``backend/migrations/``, not the
conventional ``backend/alembic/``. ``backend/`` sits on ``sys.path`` beside
``app/``, and a directory named ``alembic`` there would be picked up as a
namespace package, shadowing the installed ``alembic`` package.
"""
import logging
import os
import sys

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make `backend/` importable so `app.*` resolves when alembic runs standalone.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings  # noqa: E402  (after sys.path setup)
from app.models import SQLModel  # noqa: E402


def _configure_alembic_logging() -> None:
    """Log Alembic's own messages — and touch nothing else.

    The generated env.py template calls `fileConfig(alembic.ini)`, whose
    `[loggers]` section sets the **root** logger to WARNING and swaps in its
    own handler. This runs inside the server on every boot, so afterwards
    every INFO line the application writes (request logs, the dev
    password-reset code the README documents) disappeared while uvicorn's own
    lines survived. Alembic gets a private handler instead; root stays as the
    application configured it.
    """
    alembic_logger = logging.getLogger("alembic")
    # Alembic pre-installs a NullHandler on its own logger, so "does it have a
    # handler?" is the wrong question — with propagate=False a NullHandler
    # alone would swallow every migration line. Add a real handler unless one
    # is already there.
    if all(isinstance(h, logging.NullHandler) for h in alembic_logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)-5.5s [%(name)s] %(message)s"))
        alembic_logger.addHandler(handler)
    alembic_logger.setLevel(logging.INFO)
    alembic_logger.propagate = False

    # SQL text is noise; errors still surface (alembic.ini used to set this).
    for name in ("sqlalchemy.engine", "sqlalchemy.engine.Engine", "sqlalchemy.pool"):
        logging.getLogger(name).setLevel(logging.WARNING)


_configure_alembic_logging()

config = context.config

# `%` is ConfigParser's interpolation char; escape it rather than let a
# percent-encoded URL (password, sslmode) blow up on read-back.
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))

# The single source of truth for the schema: the SQLModel models themselves.
# Autogenerate diffs this against the live database.
target_metadata = SQLModel.metadata


def include_object(object_, name, type_, reflected, compare_to) -> bool:
    """Skip tables that don't belong to the app (e.g. an ORM package's own)."""
    if type_ == "table" and name.startswith("_"):
        return False
    return True


def run_migrations_offline() -> None:
    """Emit SQL without a live connection — `alembic upgrade head --sql`."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Compare column types by value, not spelling: SQLite reports
            # VARCHAR(n) while the model says String(n), and vice versa.
            compare_type=True,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
