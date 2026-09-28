"""P0 regression tests.

1. /auth/reset-confirm must verify the 6-digit code. Before this fix it only
   checked that *some* code existed for the email, so anyone could take over
   any account (including platform_admin) by calling /reset-request and then
   /reset-confirm with no code at all.
2. Demo accounts with published passwords must never seed into production.
3. Boot must refuse unsafe production config (default JWT secret, ephemeral
   upload disk).
"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

from app import main as main_mod
from app import seed as seed_mod
from app.config import Settings
from app.main import app
from app.models import Course, User
from app.routers import auth as auth_router


@pytest.fixture(name="client")
def client_fixture():
    auth_router._RATE.clear()
    with TestClient(app) as c:
        yield c
    auth_router._RATE.clear()


def _signup(client, email="reset-probe@gramshiksha.in") -> str:
    r = client.post("/auth/register", json={
        "email": email, "name": "Reset Probe", "password": "Original@123",
        "role": "student"})
    assert r.status_code == 201, r.text
    return email


def test_reset_confirms_only_with_the_emailed_code(client, monkeypatch):
    email = _signup(client)
    sent: dict = {}

    def capture(to: str, code: str) -> bool:
        sent["to"], sent["code"] = to, code
        return True

    monkeypatch.setattr(auth_router, "send_reset_email", capture)
    # Keep the delivery pre-check from short-circuiting this test: on the
    # Postgres CI job the app runs in production mode, where "no SMTP
    # configured" answers 503 before the stub above would ever be consulted.
    # SMTP only has to *look* configured here — delivery is stubbed anyway.
    monkeypatch.setattr(auth_router, "settings", Settings(smtp_host="smtp.test"))

    # Request: 200 with the same shape for every address, and no code leaked.
    r = client.post("/auth/reset-request", json={"email": email})
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert "code" not in r.text
    assert sent["to"] == email
    assert len(sent["code"]) == 6 and sent["code"].isdigit()

    # No code field at all → rejected by validation (the takeover hole).
    r = client.post("/auth/reset-confirm",
                    json={"email": email, "new_password": "NewPass@1234"})
    assert r.status_code == 422

    # Wrong code → rejected.
    wrong = "000000" if sent["code"] != "000000" else "111111"
    r = client.post("/auth/reset-confirm",
                    json={"email": email, "code": wrong, "new_password": "NewPass@1234"})
    assert r.status_code == 400

    # Correct code → password changes.
    r = client.post("/auth/reset-confirm",
                    json={"email": email, "code": sent["code"], "new_password": "NewPass@1234"})
    assert r.status_code == 200, r.text
    assert client.post("/auth/token",
                       data={"username": email, "password": "NewPass@1234"}).status_code == 200
    assert client.post("/auth/token",
                       data={"username": email, "password": "Original@123"}).status_code == 401

    # Single use: the code cannot be replayed.
    r = client.post("/auth/reset-confirm",
                    json={"email": email, "code": sent["code"], "new_password": "Third@12345"})
    assert r.status_code == 400


def test_reset_request_is_rate_limited(client):
    _signup(client, "ratelimit-probe@gramshiksha.in")
    codes = [client.post("/auth/reset-request",
                         json={"email": "ratelimit-probe@gramshiksha.in"})
             for _ in range(auth_router.RATE_LIMIT + 1)]
    assert codes[-1].status_code == 429


def test_undeliverable_reset_answers_503_for_everyone(client, monkeypatch):
    """Production without SMTP must fail loudly — and identically for existing
    and non-existing accounts, or the status code alone would enumerate users."""
    monkeypatch.setattr(auth_router, "settings",
                        Settings(database_url="postgresql+psycopg://u:p@host/db",
                                 jwt_secret="x" * 64))
    known = client.post("/auth/reset-request",
                        json={"email": "student1@gramshiksha.in"})
    unknown = client.post("/auth/reset-request",
                          json={"email": "definitely-not-a-user@x.in"})
    assert known.status_code == 503
    assert unknown.status_code == known.status_code
    assert "code" not in known.text.lower()


def test_boot_guard_blocks_default_jwt_secret(monkeypatch):
    unsafe = Settings(
        database_url="postgresql+psycopg://user:pass@host/db?sslmode=require",
        jwt_secret="dev-secret-change-me",
        cloudinary_cloud_name="c", cloudinary_api_key="k", cloudinary_api_secret="s")
    monkeypatch.setattr(main_mod, "settings", unsafe)
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        main_mod.check_production_safety()


def test_boot_guard_blocks_ephemeral_upload_disk(monkeypatch):
    unsafe = Settings(database_url="postgresql+psycopg://user:pass@host/db",
                      jwt_secret="x" * 64)
    monkeypatch.setattr(main_mod, "settings", unsafe)
    with pytest.raises(RuntimeError, match="ephemeral"):
        main_mod.check_production_safety()


def test_boot_guard_passes_when_hardened(monkeypatch):
    safe = Settings(database_url="postgresql+psycopg://user:pass@host/db",
                    jwt_secret="x" * 64,
                    cloudinary_cloud_name="c", cloudinary_api_key="k",
                    cloudinary_api_secret="s",
                    smtp_host="smtp.example.com")
    monkeypatch.setattr(main_mod, "settings", safe)
    main_mod.check_production_safety()  # must not raise


def test_boot_guard_is_inert_on_local_sqlite(monkeypatch):
    # Dev stays ergonomic: SQLite + dev secret must never block startup.
    monkeypatch.setattr(main_mod, "settings",
                        Settings(database_url="sqlite:///./x.db",
                                 jwt_secret="dev-secret-change-me"))
    main_mod.check_production_safety()


def test_production_seed_creates_no_demo_accounts(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path}/fresh.db")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(seed_mod, "settings", Settings(seed_demo="false"))

    with Session(engine) as s:
        seed_mod.seed(s)
        # No users at all — most importantly no admin@gramshiksha.in.
        assert s.exec(select(User)).all() == []
        # Real content still seeds, just without demo teachers attached.
        courses = s.exec(select(Course)).all()
        assert len(courses) >= 9
        assert all(c.teacher_id is None for c in courses)
