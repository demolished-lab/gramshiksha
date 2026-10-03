"""Smart Book Finder: tier order, honest ETA, and a queue that fulfils itself.

Contract under test:
* tier 1 (already catalogued) answers immediately with `eta_seconds: 0`;
* tier 2 (live official scan) creates the Textbook row on the spot — the PDF
  url is the idempotency anchor, so a repeated locate can never duplicate;
* tier 3 queues the ask with a real position, deduped and honest about ETA;
* keep-warm's `scan-requests` fulfils pendings, notifies the requester, then
  cools down instead of turning into a crawl cannon;
* `GET /library/requests` needs a session and shows only your own asks.

Every path is a bare string literal — the route-coverage canary parses source
with `ast`, so f-strings/variables there would be invisible to it. All live
portal traffic is monkeypatched: tests never crawl eBalbharati.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect as sa_inspect
from sqlmodel import Session, select

from app.db import engine
from app.main import app
from app.models import BookRequest, Notification, Textbook
from app.routers import library

# Private board + fake PDF ids: the suite shares one database, so probe rows
# must be recognisably ours to be cleaned up (and must never appear in
# /textbooks/coverage, which asserts exactly the three real boards).
BOARD = "Finder Test Board"
FAKE_PDF = "https://ebooks.ebalbharati.in/pdfs/99990000{}.pdf"
LIB_TITLE = "Finder Probe Book"
OFFICIAL_TITLE = "Finder Official Hit"
QUEUED_TITLE = "Finder Queue Book"
FULFIL_TITLE = "Finder Fulfilled Book"
MINE_TITLE = "Finder Mine Book"

HIT = {"book_id": "999900002", "title": OFFICIAL_TITLE,
       "pdf": FAKE_PDF.format(2),
       "cover": "https://books.ebalbharati.in/BookCovers/999900002.jpg",
       "lang": "mr"}


@pytest.fixture(name="client")
def client_fixture():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _probe_rows_do_not_outlive_their_test():
    """Requests and notifications go first: BookRequest.textbook_id points at
    a Textbook, and a dangling reference would break the next run's ingest."""
    yield
    # The pure matcher tests below run before any TestClient has booted the
    # app — and booting it is what runs `alembic upgrade head`, so on the
    # very first tests of a fresh suite this schema may not exist yet.
    if not sa_inspect(engine).has_table("bookrequest"):
        return
    with Session(engine) as s:
        for r in s.exec(select(BookRequest).where(
                BookRequest.query.like("finder%"))).all():
            s.delete(r)
        for n in s.exec(select(Notification).where(
                Notification.type == "book_available")).all():
            if "Finder" in (n.payload or ""):
                s.delete(n)
        for t in s.exec(select(Textbook).where(
                (Textbook.board == BOARD)
                | Textbook.deep_url.like(f"{FAKE_PDF[:-6]}%"))).all():
            s.delete(t)
        s.commit()


def register(client, email):
    r = client.post("/auth/register", json={
        "email": email, "name": "Finder Student", "password": "Finder@123",
        "role": "student", "class_grade": 8, "board": "Maharashtra SSC"})
    assert r.status_code == 201, r.text
    body = r.json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body["id"]


def no_scan(q, grade, pref, deadline):
    """Tier 2 stub for 'the portal honestly has nothing'."""
    return [], ["mr"]


class TestFuzzyMatch:
    """The matcher decides whether tier 2 is even worth firing."""

    def test_matches_a_real_book_under_digit_and_wording_noise(self):
        # "गणित 8" vs "८ वी गणित": Devanagari digits, class prefix, medium word.
        assert library.fuzzy_match("गणित 8", "८ वी गणित") is True
        assert library.fuzzy_match("गणित", "गणित भाग-१") is True      # containment
        assert library.fuzzy_match("इतिहास", "इतिहास व संस्कृती") is True

    def test_does_not_swallow_the_whole_class(self):
        assert library.fuzzy_match("इतिहास", "गणित") is False
        assert library.fuzzy_match("Science8", "सायन्स ऍन्ड टेक्नॉलॉजी") is False
        assert library.fuzzy_match("", "गणित") is False
        assert library.fuzzy_match("गणित", "") is False


def test_locate_answers_instantly_for_an_already_catalogued_book(client):
    with Session(engine) as s:
        row = Textbook(board=BOARD, class_grade=8, subject_name="Finder Probe",
                       lang="en", title=LIB_TITLE,
                       source_url="https://books.ebalbharati.in/probe",
                       deep_url=FAKE_PDF.format(1), last_ok=True)
        s.add(row)
        s.commit()
        tid = row.id

    r = client.post("/library/locate", json={"q": LIB_TITLE, "class_grade": 8})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["result"] == "found" and data["source"] == "library"
    assert data["eta_seconds"] == 0                 # nothing to wait for
    assert data["books"][0]["id"] == tid
    assert data["books"][0]["has_deep_link"] is True
    assert data["elapsed_s"] >= 0
    # production mount twin (route-coverage canary reads these literals)
    assert client.post("/api/library/locate",
                       json={"q": LIB_TITLE}).status_code == 200
    # an empty search is a client mistake, not a queue entry
    assert client.post("/library/locate", json={"q": "   "}).status_code == 422


def test_locate_queues_when_nothing_official_matches(client, monkeypatch):
    monkeypatch.setattr(library, "scan_official", no_scan)
    r = client.post("/library/locate", json={
        "q": QUEUED_TITLE, "class_grade": 8, "board": BOARD, "lang": "mr"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["result"] == "queued" and data["pending"] is True
    assert data["position"] >= 1
    assert data["scanned_langs"] == ["mr"]
    assert data["eta_seconds"] == 10               # one medium, honestly
    assert data["elapsed_s"] >= 0
    with Session(engine) as s:
        row = s.exec(select(BookRequest).where(
            BookRequest.query == QUEUED_TITLE.lower())).first()
        assert row is not None and row.status == "pending"
        assert row.user_id is None                 # anonymous ask still counts
    # the same ask twice must not double the line
    again = client.post("/library/locate", json={
        "q": QUEUED_TITLE, "class_grade": 8, "board": BOARD, "lang": "mr"})
    with Session(engine) as s:
        n = len(s.exec(select(BookRequest).where(
            BookRequest.query == QUEUED_TITLE.lower())).all())
    assert again.json()["position"] == n == 1


def test_locate_scans_the_official_portal_and_ingests_one_row(client, monkeypatch):
    calls = []

    def fake_scan(q, grade, pref, deadline):
        calls.append((q, grade, tuple(pref)))
        return [dict(HIT, title=OFFICIAL_TITLE, pdf=FAKE_PDF.format(2))], ["mr"]

    monkeypatch.setattr(library, "scan_official", fake_scan)
    r = client.post("/library/locate", json={"q": OFFICIAL_TITLE, "class_grade": 8})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["result"] == "found" and data["source"] == "official"
    assert data["scanned_langs"] == ["mr"]
    book = data["books"][0]
    assert book["has_deep_link"] is True
    with Session(engine) as s:
        row = s.get(Textbook, book["id"])
        assert row is not None and row.last_ok is True
        assert row.deep_url == FAKE_PDF.format(2)
        assert row.subject_name                    # fallback never leaves it blank
        assert row.board in ("Maharashtra SSC", "Maharashtra HSC")

    # Re-locate: tier 1 now has it, the portal is never hit twice.
    again = client.post("/library/locate", json={"q": OFFICIAL_TITLE, "class_grade": 8})
    assert again.json()["source"] == "library"
    assert [b["id"] for b in again.json()["books"]] == [book["id"]]
    assert len(calls) == 1
    with Session(engine) as s:
        rows = s.exec(select(Textbook).where(
            Textbook.deep_url == FAKE_PDF.format(2))).all()
    assert len(rows) == 1                           # the anchor held


def test_scan_requests_fulfils_notifies_and_then_cools_down(client, monkeypatch):
    h, uid = register(client, "finder-scan@x.in")

    # 1. a learner asks for a book the library doesn't have yet
    monkeypatch.setattr(library, "scan_official", no_scan)
    assert client.post("/library/locate",
                       json={"q": FULFIL_TITLE, "class_grade": 8, "lang": "mr"},
                       headers=h).json()["result"] == "queued"
    with Session(engine) as s:
        req = s.exec(select(BookRequest).where(
            BookRequest.query == FULFIL_TITLE.lower())).one()
        req_id = req.id

    # 2. the publisher lists it → the next keep-warm pass must pick it up
    monkeypatch.setattr(library, "scan_official",
                        lambda q, g, pref, d: (
                            [dict(HIT, title=FULFIL_TITLE,
                                  pdf=FAKE_PDF.format(3))], ["mr"]))
    monkeypatch.setattr(library, "_last_scan_at", [0.0])  # reset module clock
    r = client.post("/library/scan-requests")
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["found"] >= 1 and "pending" in out
    with Session(engine) as s:
        req = s.get(BookRequest, req_id)
        assert req.status == "found" and req.textbook_id and req.found_at
        notes = s.exec(select(Notification).where(
            Notification.user_id == uid,
            Notification.type == "book_available")).all()
        assert any(str(req_id) in (n.payload or "") for n in notes)

    # 3. an immediate second pass must cool down, not crawl again
    again = client.post("/library/scan-requests")
    assert again.status_code == 200 and again.json().get("skipped") is True


def test_my_requests_is_yours_and_needs_a_session(client, monkeypatch):
    assert client.get("/library/requests").status_code == 401
    h, _uid = register(client, "finder-me@x.in")
    monkeypatch.setattr(library, "scan_official", no_scan)
    client.post("/library/locate", json={"q": MINE_TITLE, "class_grade": 8},
                headers=h)

    r = client.get("/library/requests", headers=h)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert any(x["query"] == MINE_TITLE.lower()
               and x["status"] == "pending" for x in rows)
    assert all(set(x) == {"id", "query", "class_grade", "status",
                          "textbook_id", "stream", "created_at", "found_at"} for x in rows)
    # production mount twin
    assert client.get("/api/library/requests", headers=h).status_code == 200
