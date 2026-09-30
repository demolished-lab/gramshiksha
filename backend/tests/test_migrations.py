"""Migration coverage — schemas now come from Alembic, not create_all().

Four properties that make schema changes safe:

* a fresh database is built entirely by `alembic upgrade head`,
* a pre-Alembic database (how production was actually created) is *stamped*
  rather than re-created — existing tables and rows survive,
* a stamped database still receives what head expects of it: tables from
  create_all() in the legacy branch, columns from the idempotent shims,
* the models and the migration head must not drift: if someone edits
  models.py without generating a revision, this suite fails instead of the
  first production deploy.
"""
from sqlalchemy import create_engine, inspect, text
from sqlmodel import SQLModel

from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from app import config as config_mod
from app import db as dbmod
from app.config import Settings


def _point_at(tmp_path, monkeypatch, name):
    """Send BOTH the app engine and alembic's env.py to a throwaway database.

    env.py reads `app.config.settings` at every run, so patching the module
    attribute is what redirects the migration — patching only db.engine would
    inspect one database and migrate another.
    """
    url = f"sqlite:///{tmp_path / name}"
    monkeypatch.setattr(config_mod, "settings", Settings(database_url=url, jwt_secret="x" * 64))
    engine = create_engine(url)
    monkeypatch.setattr(dbmod, "engine", engine)
    return url, engine


def test_fresh_database_is_built_entirely_by_migrations(tmp_path, monkeypatch):
    _, engine = _point_at(tmp_path, monkeypatch, "fresh.db")

    dbmod.create_db_and_tables()

    with engine.connect() as conn:
        tables = set(inspect(engine).get_table_names())
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()

    assert "alembic_version" in tables
    assert {"user", "school", "material", "progress", "passwordresetcode"} <= tables

    head = ScriptDirectory.from_config(dbmod._alembic_config()).get_current_head()
    assert version == head, "database is not at the migration head"


def test_pre_alembic_database_is_stamped_not_recreated(tmp_path, monkeypatch):
    """Production databases were created by SQLModel.create_all(), before
    Alembic existed. Replaying the baseline would try to CREATE tables that
    already exist — boot must stamp those databases instead, keeping data."""
    _, engine = _point_at(tmp_path, monkeypatch, "legacy.db")
    SQLModel.metadata.create_all(engine)          # the pre-Alembic shape
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO board (name) VALUES ('Legacy Board')"))

    dbmod.create_db_and_tables()                  # must not raise

    with engine.connect() as conn:
        boards = conn.execute(text("SELECT COUNT(*) FROM board")).scalar_one()
        stamps = conn.execute(text("SELECT COUNT(*) FROM alembic_version")).scalar_one()
    assert boards == 1, "existing rows must survive boot"
    assert stamps == 1, "legacy database was never stamped at head"


def test_models_and_migration_head_do_not_drift(tmp_path, monkeypatch):
    _, engine = _point_at(tmp_path, monkeypatch, "drift.db")
    dbmod.create_db_and_tables()

    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={
            "compare_type": True,
            "target_metadata": SQLModel.metadata,
        })
        diffs = compare_metadata(ctx, SQLModel.metadata)

    assert diffs == [], (
        "models.py and the migration head disagree. Generate a revision:\n"
        "  cd backend && .venv/Scripts/python -m alembic revision "
        "--autogenerate -m 'describe the change'\n"
        + "\n".join(f"  {d!r}" for d in diffs)
    )


def test_stamped_database_gains_post_baseline_tables_and_columns(tmp_path, monkeypatch):
    """A stamped database is *claimed* to be at head, but boot never replays a
    revision against it — so everything head expects has to be supplied by the
    legacy branch itself: new tables by create_all(), new columns on existing
    tables by the idempotent shims.

    Built as the oldest shape still in the wild: a `user` table from before
    the approval workflow, no alembic_version, and one row that must survive.
    """
    _, engine = _point_at(tmp_path, monkeypatch, "legacy-old.db")
    with engine.begin() as conn:
        conn.execute(text(
            'CREATE TABLE "user" (id INTEGER PRIMARY KEY, email VARCHAR NOT NULL, '
            "name VARCHAR NOT NULL, hashed_password VARCHAR NOT NULL, role VARCHAR NOT NULL)"
        ))
        conn.execute(text(
            "INSERT INTO \"user\" (email, name, hashed_password, role) "
            "VALUES ('old@x.in', 'Old User', 'hash', 'teacher')"
        ))

    dbmod.create_db_and_tables()                   # must not raise

    columns = {c["name"] for c in inspect(engine).get_columns("user")}
    tables = set(inspect(engine).get_table_names())
    assert "role_status" in columns, (
        "stamped databases never replay revisions, so a new model column "
        "would be invisible to every User query until the shim adds it"
    )
    assert {"batch", "school", "passwordresetcode"} <= tables, (
        "the stamp asserts head, so head's tables must exist as well"
    )

    with engine.connect() as conn:
        status = conn.execute(text('SELECT role_status FROM "user"')).scalar_one()
        rows = conn.execute(text('SELECT COUNT(*) FROM "user"')).scalar_one()
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    assert status == "active", "pre-existing accounts are approved by definition"
    assert rows == 1, "existing rows must survive boot"
    assert version == ScriptDirectory.from_config(dbmod._alembic_config()).get_current_head()
