"""NCERT chapter editions: CBSE books read chapter-by-chapter in-app.

Contract under test:
* only (grade, subject, lang) combos whose codes returned HTTP 200 live get
  chapters (`has_chapters`), gated additionally on board == "CBSE" so a
  same-named Balbharati row can never serve the wrong curriculum;
* `?chapter=N` proxies the HEAD-verified chapter PDF from our own origin
  (same frame headers as whole-book /open); a fetch failure is an honest
  404 the reader treats as "no further chapters" — never a redirect;
* `?chapter=N&dl=1` saves that chapter as an attachment.

Every path is a bare string literal because the route-coverage canary
parses test source with `ast`.
"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

import app.routers.catalog as catalog
from app.db import engine
from app.main import app
from app.models import Textbook
from app.ncert import NCERT_CODES, chapter_url, ncert_code


@pytest.fixture(name="client")
def client_fixture():
    with TestClient(app) as c:
        yield c


def cbse_science_10_id() -> int:
    with Session(engine) as s:
        row = s.exec(select(Textbook).where(
            Textbook.board == "CBSE", Textbook.class_grade == 10,
            Textbook.subject_name == "Science", Textbook.lang == "en")).first()
        assert row is not None and row.id is not None
        return row.id


def test_mapping_covers_only_live_verified_codes():
    assert ncert_code(10, "Science", "en") == "jesc1"
    assert ncert_code(10, "Science", "hi") == "jhsc1"
    assert ncert_code(12, "Mathematics", "en") == "lemh1"
    assert ncert_code(3, "Mathematics", "en") == "cemm1"  # current NCF edition
    assert ncert_code(3, "English", "en") == "cesa1"  # Santoor, not Marigold
    assert ncert_code(9, "English", "en") == "iebe1"  # Kaveri, the listed reader
    assert ncert_code(12, "Civics", "en") == "leps1"  # Book I
    assert chapter_url("jesc1", 1).endswith("/jesc101.pdf")
    assert chapter_url("jesc1", 12).endswith("/jesc112.pdf")
    # shared names outside the verified set stay on the Find flow
    assert ncert_code(10, "Marathi", "en") is None
    assert ncert_code(6, "Science", "en") is not None
    assert ncert_code(1, "English", "en") is None  # no such NCERT book
    assert ncert_code(None, "Science", "en") is None
    assert ncert_code(9, "History", "en") is None  # integrated SST only
    assert len(NCERT_CODES) == 104


def test_list_flags_chapter_books(client):
    books = client.get("/textbooks", params={
        "class_grade": 10, "board": "CBSE"}).json()
    by_title = {b["title"]: b for b in books}
    assert by_title["Science — Class 10 (NCERT)"]["has_chapters"] is True
    assert by_title["Marathi — Class 10 (NCERT)"]["has_chapters"] is False
    ssc = client.get("/textbooks", params={
        "class_grade": 8, "board": "Maharashtra SSC"}).json()
    assert all(b["has_chapters"] is False for b in ssc)


def test_chapter_proxies_from_our_origin(client, monkeypatch):
    tid = cbse_science_10_id()
    seen: list[tuple[str, int]] = []
    monkeypatch.setattr(
        catalog, "fetch_ncert_chapter",
        lambda code, n: seen.append((code, n)) or b"%PDF-1.7\nfake chapter\n%%EOF")
    r = client.get(f"/textbooks/{tid}/open", params={"chapter": 1},
                   follow_redirects=False)
    assert r.status_code == 200, r.text
    assert "location" not in r.headers
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content.startswith(b"%PDF")
    assert seen == [("jesc1", 1)]
    assert r.headers["x-frame-options"] == "SAMEORIGIN"
    assert "frame-ancestors 'self'" in r.headers["content-security-policy"]
    assert "ch1" in r.headers["content-disposition"]
    # save mode travels with the chapter
    d = client.get(f"/textbooks/{tid}/open", params={"chapter": 2, "dl": 1})
    assert d.status_code == 200
    assert d.headers["content-disposition"].startswith("attachment; ")
    assert seen[-1] == ("jesc1", 2)
    # ...and the pager's HEAD probe resolves the same chapter — existence
    # only, no bytes downloaded, no click counted.
    monkeypatch.setattr(catalog, "chapter_exists", lambda code, n: True)
    h = client.head(f"/textbooks/{tid}/open", params={"chapter": 2})
    assert h.status_code == 200
    assert h.content == b""


def test_chapter_miss_is_404_not_redirect(client, monkeypatch):
    tid = cbse_science_10_id()
    monkeypatch.setattr(catalog, "fetch_ncert_chapter", lambda code, n: None)
    monkeypatch.setattr(catalog, "chapter_exists", lambda code, n: False)
    r = client.get(f"/textbooks/{tid}/open", params={"chapter": 99},
                   follow_redirects=False)
    assert r.status_code == 404
    assert "location" not in r.headers
    # the pager's HEAD probe sees the same answer, without counting a click
    h = client.head(f"/textbooks/{tid}/open", params={"chapter": 99})
    assert h.status_code == 404


def test_chapter_refuses_unmapped_boards(client, monkeypatch):
    books = client.get("/textbooks", params={
        "class_grade": 8, "board": "Maharashtra SSC"}).json()
    tid = books[0]["id"]
    monkeypatch.setattr(
        catalog, "fetch_ncert_chapter",
        lambda code, n: (_ for _ in ()).throw(AssertionError("must not fetch")))
    # same grade/subject/lang as a mapped CBSE row, wrong curriculum → 404
    r = client.get(f"/textbooks/{tid}/open", params={"chapter": 1},
                   follow_redirects=False)
    assert r.status_code == 404
