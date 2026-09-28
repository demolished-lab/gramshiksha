import os
import tempfile

import pytest

# Must run before app.config is imported anywhere.
_tmpdir = tempfile.mkdtemp(prefix="gramshiksha-test-")
# A local URL (or none at all) always means "point at a throwaway file" —
# otherwise `pytest` with the dev DATABASE_URL exported would write rows into
# the developer's real gramshiksha.db. A *non*-SQLite URL is honoured, so the
# CI job that provisions a Postgres service actually exercises the Postgres
# dialect instead of quietly running on SQLite.
_db = os.environ.get("DATABASE_URL", "")
if not _db or _db.startswith("sqlite"):
    os.environ["DATABASE_URL"] = f"sqlite:///{_tmpdir}/test.db"
os.environ.setdefault("JWT_SECRET", "test-secret")


@pytest.fixture(autouse=True)
def _rate_limiter_isolation():
    """Every test starts with empty buckets. Limits are keyed per IP per
    endpoint and every test shares the TestClient's single "testclient" IP, so
    without this, tests would bleed into each other and flake."""
    from app.ratelimit import clear

    clear()
    yield
    clear()


@pytest.fixture(autouse=True)
def _isolated_uploads(tmp_path_factory):
    """Keep test uploads out of the real backend/uploads directory — otherwise
    every pytest run litters the developer's uploads folder with fixture PDFs."""
    from app import storage

    original = storage.UPLOAD_DIR
    storage.UPLOAD_DIR = str(tmp_path_factory.mktemp("uploads"))
    yield
    storage.UPLOAD_DIR = original
