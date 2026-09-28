import os

from sqlmodel import Session, SQLModel, create_engine, text
from sqlalchemy import inspect
from sqlalchemy.pool import StaticPool

from .config import settings

connect_args = {}
engine_kwargs: dict = {}

if settings.database_url.startswith("sqlite"):
    # FastAPI threadpool + SQLite: share one connection across threads.
    engine_kwargs["connect_args"] = {"check_same_thread": False}
    engine_kwargs["poolclass"] = StaticPool
else:
    # Neon/Postgres in production.
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_size"] = 5
    engine_kwargs["max_overflow"] = 5

engine = create_engine(settings.database_url, **engine_kwargs)

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _alembic_config():
    """Alembic config pinned to this checkout.

    The script location is absolute, so migrations resolve the same whether
    the process started from the repo root, backend/ or somewhere in CI —
    `alembic.ini`'s relative default would depend on the working directory.
    """
    from alembic.config import Config

    cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location",
                        os.path.join(BACKEND_DIR, "migrations").replace("\\", "/"))
    return cfg


def upgrade_to_head() -> None:
    """Bring the schema to head — the *only* way tables/columns get created now.

    Databases built before Alembic was introduced (plain SQLModel.create_all)
    already match the models but carry no alembic_version row: they're stamped
    at head rather than re-run through the baseline, which would fail on
    tables that already exist. Everything newer than that stamp applies here.
    """
    from alembic import command

    tables = inspect(engine).get_table_names()
    if tables and "alembic_version" not in tables:
        command.stamp(_alembic_config(), "head")
    command.upgrade(_alembic_config(), "head")


def create_db_and_tables() -> None:
    upgrade_to_head()
    # Defensive: pre-Alembic databases were patched column-by-column here, so
    # keep the shim (idempotent, no-op once a revision owns those columns).
    ensure_textbook_columns()


def ensure_textbook_columns() -> None:
    """Lightweight migration: create_all() never ALTERs existing tables, so new
    Textbook columns are added here idempotently (SQLite + Postgres)."""
    from sqlalchemy import inspect

    insp = inspect(engine)
    if "textbook" not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns("textbook")}
    dialect = engine.dialect.name
    wants: list[tuple[str, str, str]] = [  # (name, sqlite ddl, postgres ddl)
        ("deep_url", "TEXT NOT NULL DEFAULT ''", "TEXT NOT NULL DEFAULT ''"),
        ("cover_url", "TEXT NOT NULL DEFAULT ''", "TEXT NOT NULL DEFAULT ''"),
        ("clicks", "INTEGER NOT NULL DEFAULT 0", "INTEGER NOT NULL DEFAULT 0"),
        ("last_checked", "VARCHAR", "VARCHAR"),
        ("last_ok", "INTEGER NOT NULL DEFAULT 1", "BOOLEAN NOT NULL DEFAULT TRUE"),
    ]
    missing = [(n, s, p) for n, s, p in wants if n not in existing]
    if not missing:
        return
    with engine.begin() as conn:
        for name, sqlite_ddl, pg_ddl in missing:
            ddl = pg_ddl if dialect != "sqlite" else sqlite_ddl
            exists = "IF NOT EXISTS " if dialect != "sqlite" else ""
            conn.execute(text(f"ALTER TABLE textbook ADD COLUMN {exists}{name} {ddl}"))


def get_session():
    with Session(engine) as session:
        yield session
