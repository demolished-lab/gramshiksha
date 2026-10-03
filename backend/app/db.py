import os

from sqlmodel import Session, SQLModel, create_engine, text
from sqlalchemy import inspect
from sqlalchemy.pool import StaticPool

from .config import settings

connect_args = {}
engine_kwargs: dict = {}

if settings.database_url.startswith("sqlite"):
    # FastAPI handlers run in a threadpool. File-backed SQLite must use the
    # normal per-thread connection pool; sharing one connection with
    # StaticPool corrupts concurrent result streams. StaticPool is safe and
    # necessary only for an in-memory database whose schema must be shared.
    engine_kwargs["connect_args"] = {"check_same_thread": False}
    if ":memory:" in settings.database_url or settings.database_url == "sqlite://":
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
        # Stamping asserts "this schema is at head", which is only true when
        # the database also has every table head knows about (batch,
        # passwordresetcode, ...). create_all() only ever *adds* missing
        # tables, so it is safe here — and it stops the stamp from lying.
        SQLModel.metadata.create_all(engine)
        command.stamp(_alembic_config(), "head")
    command.upgrade(_alembic_config(), "head")


def create_db_and_tables() -> None:
    upgrade_to_head()
    # Defensive: pre-Alembic databases were patched column-by-column here, so
    # keep the shims (idempotent, no-op once a revision owns those columns).
    ensure_textbook_columns()
    ensure_user_columns()
    ensure_stream_columns()


def _add_missing_columns(table: str, wants: list[tuple[str, str, str]]) -> None:
    """Add the (name, sqlite ddl, postgres ddl) columns that `table` lacks.

    Two reasons this has to exist: create_all() never ALTERs an existing
    table, and a stamped legacy database never replays revisions. The table
    name is quoted because `user` is a reserved word on Postgres.
    """
    insp = inspect(engine)
    if table not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns(table)}
    dialect = engine.dialect.name
    missing = [(n, s, p) for n, s, p in wants if n not in existing]
    if not missing:
        return
    with engine.begin() as conn:
        for name, sqlite_ddl, pg_ddl in missing:
            ddl = pg_ddl if dialect != "sqlite" else sqlite_ddl
            exists = "IF NOT EXISTS " if dialect != "sqlite" else ""
            conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN {exists}{name} {ddl}'))


def ensure_textbook_columns() -> None:
    """Lightweight migration: new Textbook columns are added here idempotently
    (SQLite + Postgres) — no-op once a revision owns them."""
    _add_missing_columns("textbook", [
        ("deep_url", "TEXT NOT NULL DEFAULT ''", "TEXT NOT NULL DEFAULT ''"),
        ("cover_url", "TEXT NOT NULL DEFAULT ''", "TEXT NOT NULL DEFAULT ''"),
        ("clicks", "INTEGER NOT NULL DEFAULT 0", "INTEGER NOT NULL DEFAULT 0"),
        ("last_checked", "VARCHAR", "VARCHAR"),
        ("last_ok", "INTEGER NOT NULL DEFAULT 1", "BOOLEAN NOT NULL DEFAULT TRUE"),
        ("part_label", "TEXT NOT NULL DEFAULT ''", "TEXT NOT NULL DEFAULT ''"),
    ])


def ensure_user_columns() -> None:
    """Give stamped pre-Alembic databases the `role_status` approval column.

    Added after the baseline revision, so those databases are stamped at a
    head that already expects it and would otherwise fail every User query on
    the first request. Idempotent, and a no-op wherever the migration ran.
    """
    _add_missing_columns("user", [
        ("role_status", "VARCHAR NOT NULL DEFAULT 'active'",
         "VARCHAR NOT NULL DEFAULT 'active'"),
    ])


def ensure_stream_columns() -> None:
    """Give stamped pre-Alembic databases the stream-categorization column.

    Same story as role_status: the stamp claims head, so every table head
    knows about must exist with every column. Idempotent, no-op post-migration.
    """
    for table in ("textbook", "subject", "material", "bookrequest",
                  "readingpick", "doubt"):
        _add_missing_columns(table, [
            ("stream", "TEXT NOT NULL DEFAULT ''", "TEXT NOT NULL DEFAULT ''"),
        ])


def get_session():
    with Session(engine) as session:
        yield session
