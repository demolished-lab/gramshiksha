"""Production-readiness tests: coverage, /api parity, auth leaks, headers."""
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from app.routers import auth as auth_router


@pytest.fixture(name="client")
def client_fixture():
    auth_router._RATE.clear()  # isolate in-process rate limiter between tests
    with TestClient(app) as c:
        yield c
    auth_router._RATE.clear()


def login(client, email, password):
    r = client.post("/auth/token", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_textbooks_full_coverage(client):
    for board in ["Maharashtra SSC", "Maharashtra HSC", "CBSE"]:
        for grade in range(1, 13):
            r = client.get("/textbooks", params={"class_grade": grade, "board": board})
            assert r.status_code == 200, (board, grade, r.text)
            assert len(r.json()) >= 1, f"no textbooks for {board} class {grade}"


def test_textbooks_portals_and_coverage(client):
    portals = client.get("/textbooks/portals").json()
    assert any("ePathshala" in p["name"] for p in portals)
    assert any("Balbharati" in p["name"] for p in portals)
    cov = client.get("/textbooks/coverage").json()
    assert set(cov) == {"Maharashtra SSC", "Maharashtra HSC", "CBSE"}


def test_api_prefix_parity(client):
    plain = client.get("/textbooks", params={"class_grade": 8, "board": "Maharashtra SSC"}).json()
    prefixed = client.get("/api/textbooks", params={"class_grade": 8, "board": "Maharashtra SSC"}).json()
    assert plain == prefixed
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/ready").json()["status"] in ("ready", "degraded")
    assert client.get("/api/ready").json()["status"] in ("ready", "degraded")


def test_security_headers_and_no_public_uploads(client):
    r = client.get("/health")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    # upload dir must not be publicly browsable (files only via authed download)
    assert client.get("/uploads/anything.pdf").status_code == 404
    assert client.get("/api/uploads/anything.pdf").status_code == 404


def test_reset_request_does_not_leak_code(client, monkeypatch):
    # Delivery is stubbed so this asserts the *response shape* only — the real
    # delivery/503 contract lives in test_reset_and_guards.py, and this file
    # must pass on both the SQLite and the Postgres CI jobs.
    from app.routers import auth as auth_mod
    monkeypatch.setattr(auth_mod, "send_reset_email", lambda to, code: True)
    # Delivery pre-check must not 503 this on the Postgres CI job (production
    # mode, no SMTP env) — SMTP only needs to look configured; the sender above
    # is stubbed, so nothing is actually sent.
    monkeypatch.setattr(auth_mod, "settings", Settings(smtp_host="smtp.test"))

    r = client.post("/auth/reset-request", json={"email": "student1@gramshiksha.in"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}  # no code field
    r = client.post("/auth/reset-request", json={"email": "nobody@x.in"})
    assert r.status_code == 200 and r.json() == {"ok": True}


def test_courses_total_is_real_count(client):
    all_courses = client.get("/courses", params={"limit": 100}).json()
    filtered = client.get("/courses", params={"class_grade": 8, "limit": 1}).json()
    assert all_courses["total"] >= len(all_courses["items"])
    # total reflects the filter, not the page size
    full8 = client.get("/courses", params={"class_grade": 8, "limit": 100}).json()
    assert filtered["total"] == full8["total"] >= len(filtered["items"])


def test_materials_filter_applies_before_pagination(client):
    t = login(client, "teacher1@gramshiksha.in", "Teach@1234")
    r = client.post("/materials", data={
        "title": "Prod filter probe", "type": "notes", "class_grade": 3,
        "board": "CBSE", "subject_name": "Mathematics", "lang": "en",
        "visibility": "public", "source_of_content": "Created by teacher"},
        files={"file": ("probe.pdf", b"%PDF-1.4 fake", "application/pdf")}, headers=t)
    assert r.status_code == 201, r.text
    # filtering for a different grade must exclude it
    other = client.get("/materials", params={"class_grade": 11}, headers=t).json()
    assert all(m["class_grade"] == 11 for m in other)
    same = client.get("/materials", params={"class_grade": 3}, headers=t).json()
    assert any(m["title"] == "Prod filter probe" for m in same)


def test_textbooks_output_has_wrapper_fields(client):
    books = client.get("/textbooks", params={"class_grade": 8, "board": "Maharashtra SSC"}).json()
    assert books
    b = books[0]
    assert {"has_deep_link", "cover_url", "clicks"} <= set(b)


def test_open_redirect_counts_click_and_falls_back(client):
    books = client.get("/textbooks", params={"class_grade": 8, "board": "Maharashtra SSC"}).json()
    b = [x for x in books if not x["has_deep_link"]][0]
    before = b["clicks"]
    r = client.get(f"/textbooks/{b['id']}/open", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == b["source_url"]  # no deep link → portal
    after = client.get("/textbooks", params={"class_grade": 8, "board": "Maharashtra SSC"}).json()
    assert [x for x in after if x["id"] == b["id"]][0]["clicks"] == before + 1
    assert client.get("/textbooks/999999/open").status_code == 404
    assert client.get("/api/textbooks/999999/open").status_code == 404


def test_open_serves_the_pdf_from_our_own_origin(client, monkeypatch):
    """The book must appear *here* — no visible bounce to ebalbharati."""
    import app.routers.catalog as catalog
    from app.db import engine
    from app.models import Textbook
    from sqlmodel import Session, select
    with Session(engine) as s:
        t = s.exec(select(Textbook).limit(1)).one()
        tid = t.id
        t.deep_url = "https://ebooks.ebalbharati.in/pdfs/101050001.pdf"
        t.last_ok = True
        s.add(t)
        s.commit()

    seen: list[str] = []
    monkeypatch.setattr(catalog, "_fetch_pdf",
                        lambda url: seen.append(url) or b"%PDF-1.7\nfake\n%%EOF")
    try:
        r = client.get(f"/textbooks/{tid}/open", follow_redirects=False)
        assert r.status_code == 200                      # not a 302
        assert "location" not in r.headers               # nothing to follow
        assert r.headers["content-type"].startswith("application/pdf")
        assert r.content.startswith(b"%PDF")
        assert seen == ["https://ebooks.ebalbharati.in/pdfs/101050001.pdf"]
        assert r.headers["cache-control"].startswith("private")
        # framed by the in-app viewer (same origin), never by another site
        assert r.headers["x-frame-options"] == "SAMEORIGIN"
        assert "frame-ancestors 'self'" in r.headers["content-security-policy"]
        # view mode is inline with a real (Devanagari-safe) filename
        disp = r.headers["content-disposition"]
        assert disp.startswith("inline; ")
        assert "filename*=UTF-8''" in disp

        # Save = the same bytes with an attachment disposition
        d = client.get(f"/textbooks/{tid}/open", params={"dl": 1})
        assert d.status_code == 200 and d.content == r.content
        assert d.headers["content-disposition"].startswith("attachment; ")

        # opt-in "open on the publisher's site" keeps the legacy 302
        e = client.get(f"/textbooks/{tid}/open", params={"ext": 1},
                       follow_redirects=False)
        assert e.status_code == 302
        assert e.headers["location"] == "https://ebooks.ebalbharati.in/pdfs/101050001.pdf"
    finally:
        with Session(engine) as s:
            t = s.get(Textbook, tid)
            t.deep_url = ""
            t.last_ok = True
            s.add(t)
            s.commit()


def test_open_degrades_to_redirect_when_the_proxy_fails(client, monkeypatch):
    """A dead/slow/HTML-200 source must still open the book, in-frame."""
    import app.routers.catalog as catalog
    from app.db import engine
    from app.models import Textbook
    from sqlmodel import Session, select
    with Session(engine) as s:
        t = s.exec(select(Textbook).limit(1)).one()
        tid = t.id
        t.deep_url = "https://ebooks.ebalbharati.in/pdfs/101050009.pdf"
        t.last_ok = True
        s.add(t)
        s.commit()
    monkeypatch.setattr(catalog, "_fetch_pdf", lambda url: None)
    try:
        r = client.get(f"/textbooks/{tid}/open", follow_redirects=False)
        assert r.status_code == 302
        assert r.headers["location"] == "https://ebooks.ebalbharati.in/pdfs/101050009.pdf"
    finally:
        with Session(engine) as s:
            t = s.get(Textbook, tid)
            t.deep_url = ""
            t.last_ok = True
            s.add(t)
            s.commit()


def test_recheck_updates_flags(client):
    from app.db import engine
    from app.models import Textbook
    from sqlmodel import Session, select
    import app.routers.catalog as catalog
    with Session(engine) as s:
        t = s.exec(select(Textbook).limit(1)).one()
        tid = t.id
        t.deep_url = "https://example.invalid/x.pdf"
        t.last_checked = None
        s.add(t)
        s.commit()
    real = catalog.check_url
    catalog.check_url = lambda url: False  # noqa: E731 — simulate dead link
    try:
        admin = login(client, "admin@gramshiksha.in", "Admin@1234")
        r = client.post("/admin/textbooks/recheck", params={"limit": 5}, headers=admin)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["checked"] >= 1 and body["dead"] >= 1
        with Session(engine) as s:
            t = s.get(Textbook, tid)
            assert t.last_ok is False and t.last_checked
    finally:
        catalog.check_url = real
        with Session(engine) as s:
            t = s.get(Textbook, tid)
            t.deep_url = ""
            t.last_ok = True
            t.last_checked = None
            s.add(t)
            s.commit()


def test_recheck_requires_platform_admin(client):
    s = login(client, "student1@gramshiksha.in", "Learn@1234")
    assert client.post("/admin/textbooks/recheck", headers=s).status_code == 403
