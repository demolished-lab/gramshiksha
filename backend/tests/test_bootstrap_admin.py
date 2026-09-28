"""bootstrap_admin — the only supported way to gain a platform_admin on an
instance that seeded no demo accounts.

Production Postgres never seeds the demo users (SEED_DEMO=auto is off there),
so without this module a fresh deploy would have nobody able to approve
teachers — the approval workflow would be installed and unusable. Forcing
SEED_DEMO=true instead would publish README passwords on the live instance.
"""
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel, select

from app import bootstrap_admin
from app import db as dbmod
from app.models import User
from app.security import has_role, verify_password


def _point_at(tmp_path, monkeypatch, name="bootstrap.db"):
    """Send app.db's engine to a throwaway database — bootstrap_admin reads
    `db.engine` at call time, so patching the module attribute redirects it."""
    engine = create_engine(f"sqlite:///{tmp_path / name}")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(dbmod, "engine", engine)
    return engine


def test_bootstrap_creates_a_login_that_passes_the_admin_gate(tmp_path, monkeypatch):
    engine = _point_at(tmp_path, monkeypatch)

    # Mixed-case email: normalization must match how register/login store it.
    assert bootstrap_admin.main(
        ["bootstrap_admin.py", "Root@School.Ac.In", "Strong@1234"]) == 0

    with Session(engine) as s:
        user = s.exec(select(User).where(
            User.email == "root@school.ac.in")).first()
    assert user is not None, "created account must be findable by login email"
    assert user.role == "platform_admin"
    assert user.role_status == "active"
    assert has_role(user, "platform_admin")  # the gate the dashboard uses
    assert verify_password("Strong@1234", user.hashed_password)


def test_bootstrap_promotes_an_existing_account_without_duplicating(tmp_path, monkeypatch):
    engine = _point_at(tmp_path, monkeypatch)
    with Session(engine) as s:
        s.add(User(email="teacher@x.in", name="T", hashed_password="old-hash",
                   role="teacher", role_status="pending"))
        s.commit()

    assert bootstrap_admin.main(
        ["bootstrap_admin.py", "teacher@x.in", "NewPass@123"]) == 0
    assert bootstrap_admin.main(  # second run must not create a second row
        ["bootstrap_admin.py", "teacher@x.in", "NewPass@123"]) == 0

    with Session(engine) as s:
        rows = s.exec(select(User).where(User.email == "teacher@x.in")).all()
    assert len(rows) == 1
    assert rows[0].role == "platform_admin" and rows[0].role_status == "active"
    assert verify_password("NewPass@123", rows[0].hashed_password)


def test_bootstrap_refuses_usage_errors(tmp_path, monkeypatch):
    engine = _point_at(tmp_path, monkeypatch)
    # Wrong argument count, and a password the API itself would reject —
    # either would mint an account that cannot log in through the app.
    assert bootstrap_admin.main(["bootstrap_admin.py"]) == 2
    assert bootstrap_admin.main(
        ["bootstrap_admin.py", "a@b.in", "short"]) == 2

    with Session(engine) as s:
        assert s.exec(select(User)).all() == [], "nothing may be written on error"
