"""Stream categorization for Classes 11-12 (Science / Commerce / Arts &
Humanities / Vocational).

Contract under test:
* `stream_for` maps English and Marathi subject names, returns "" for
  shared subjects (languages, Mathematics, EVS) and for grades below 11 —
  streams only exist where they actually exist;
* a stream filter never hides shared subjects (`stream == X OR ""`), on
  textbooks, courses (via Subject), materials, doubts and reading picks;
* unknown stream codes are 422, everywhere;
* writers derive the stream when the caller doesn't state it (ingest,
  material upload, doubt ask, reading post);
* the availability response carries the streams actually present, and []
  below class 11.

Every path is a bare string literal because the route-coverage canary
parses test source with `ast`.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect as sa_inspect
from sqlmodel import Session, select

from app.db import engine
from app.main import app
from app.models import BookRequest, Course, Doubt, Material, ReadingPick, Subject, Textbook, User, utcnow
from app.streams import STREAM_CODES, stream_for

BOARD = "Stream Test Board"


@pytest.fixture(name="client")
def client_fixture():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _probe_rows_do_not_outlive_their_test():
    yield
    if not sa_inspect(engine).has_table("readingpick"):
        return  # the app boots (and migrates) on the first TestClient use
    with Session(engine) as s:
        for r in s.exec(select(ReadingPick).where(
                ReadingPick.title.like("Stream Probe%"))).all():
            s.delete(r)
        for t in s.exec(select(Textbook).where(
                Textbook.board == BOARD)).all():
            s.delete(t)
        for m in s.exec(select(Material).where(
                Material.board == BOARD)).all():
            s.delete(m)
        for d in s.exec(select(Doubt).where(
                Doubt.text.like("Stream probe%"))).all():
            s.delete(d)
        for q in s.exec(select(BookRequest).where(
                BookRequest.query.like("stream probe%"))).all():
            s.delete(q)
        for c in s.exec(select(Course).where(
                Course.board == BOARD)).all():
            s.delete(c)
        for sub in s.exec(select(Subject).where(
                Subject.board == BOARD)).all():
            s.delete(sub)
        for u in s.exec(select(User).where(
                User.email.like("stream-%@x.in"))).all():
            s.delete(u)
        s.commit()


def login(client, email, password="Teach@1234"):
    r = client.post("/auth/token", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def register(client, email, role="student", grade=11):
    r = client.post("/auth/register", json={
        "email": email, "name": "Stream Probe", "password": "Stream@123",
        "role": role, "class_grade": grade, "board": BOARD})
    assert r.status_code == 201, r.text
    body = r.json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body["id"]


def seed_book(session_title, subject, grade=11, lang="en"):
    with Session(engine) as s:
        row = Textbook(board=BOARD, class_grade=grade, subject_name=subject,
                       lang=lang, title=session_title,
                       source_url="https://books.ebalbharati.in/stream-probe",
                       deep_url="https://ebooks.ebalbharati.in/pdfs/99990099.pdf",
                       last_ok=True, stream=stream_for(grade, subject))
        s.add(row)
        s.commit()
        return row.id


def test_stream_mapping_only_where_streams_exist():
    assert stream_for(11, "Physics") == "science"
    assert stream_for(12, "Chemistry") == "science"
    assert stream_for(11, "Economics") == "commerce"
    assert stream_for(11, "पुस्तपालन व लेखाकर्म") == "commerce"
    assert stream_for(12, "History") == "arts"
    assert stream_for(11, "मानसशास्त्र") == "arts"
    assert stream_for(11, "बाल विकास") == "vocational"
    # shared with every stream — visible under all of them
    assert stream_for(11, "English") == ""
    assert stream_for(11, "Mathematics") == ""
    assert stream_for(12, "Computer Science") == ""
    # below class 11 there are no streams at all
    assert stream_for(10, "Physics") == ""
    assert stream_for(8, "Science") == ""
    assert stream_for(None, "Physics") == ""
    assert STREAM_CODES == {"science", "commerce", "arts", "vocational"}


def test_stream_columns_exist_after_migration(client):
    cols = {t: {c["name"] for c in sa_inspect(engine).get_columns(t)}
            for t in ("textbook", "subject", "material", "bookrequest",
                      "readingpick", "doubt")}
    assert all("stream" in names for names in cols.values())


def test_textbooks_stream_filter_keeps_shared_books(client):
    seed_book("Stream Probe Physics", "Physics")
    seed_book("Stream Probe History", "History")
    seed_book("Stream Probe English", "English")
    base = "/textbooks?class_grade=11&board=" + BOARD.replace(" ", "+")
    science = client.get(base + "&stream=science").json()
    titles = {b["title"] for b in science}
    assert "Stream Probe Physics" in titles
    assert "Stream Probe English" in titles      # common: never hidden
    assert "Stream Probe History" not in titles
    assert all(b["stream"] in ("science", "") for b in science)
    arts = client.get(base + "&stream=arts").json()
    assert {b["title"] for b in arts} == {"Stream Probe History", "Stream Probe English"}
    assert client.get(base + "&stream=bogus").status_code == 422


def test_availability_reports_only_present_streams(client):
    seed_book("Stream Probe Physics", "Physics")
    seed_book("Stream Probe English", "English")
    r = client.get("/catalog/availability?class_grade=11&board=" + BOARD.replace(" ", "+"))
    assert r.status_code == 200, r.text
    codes = {s["code"] for s in r.json()["streams"]}
    assert codes == {"science"}  # commerce/arts have no books: no empty chips
    by_name = {s["name"]: s for s in r.json()["subjects"]}
    assert by_name["Physics"]["stream"] == "science"
    assert by_name["English"]["stream"] == ""
    young = client.get("/catalog/availability?class_grade=8&board=" + BOARD.replace(" ", "+"))
    assert young.json()["streams"] == []


def test_courses_inherit_stream_from_subject(client):
    with Session(engine) as s:
        subj = Subject(name_en="Physics", name_hi="", name_mr="",
                       class_grade=11, board=BOARD, stream="science")
        s.add(subj)
        s.commit()
        s.refresh(subj)
        s.add(Course(slug="stream-probe-physics", subject_id=subj.id,
                     board=BOARD, class_grade=11, title_en="Stream Probe Course",
                     title_hi="", title_mr=""))
        s.commit()
    arts = client.get("/courses?class_grade=11&board=" + BOARD.replace(" ", "+") + "&stream=arts")
    assert arts.json()["total"] == 0
    science = client.get("/courses?class_grade=11&board=" + BOARD.replace(" ", "+") + "&stream=science")
    items = science.json()["items"]
    assert [c["slug"] for c in items] == ["stream-probe-physics"]
    assert items[0]["stream"] == "science"
    assert client.get("/courses?stream=bogus").status_code == 422


def test_reading_pick_derives_and_filters_stream(client):
    teacher = login(client, "teacher1@gramshiksha.in")
    now = utcnow()
    month = f"{now.year:04d}-{now.month:02d}"
    posted = client.post("/library/reading", json={
        "month": month, "title": "Stream Probe Physics Pick",
        "subject_name": "Physics", "class_grade": 11}, headers=teacher)
    assert posted.status_code == 200, posted.text
    assert posted.json()["stream"] == "science"  # derived, not stated
    assert posted.json()["id"] in [
        x["id"] for x in client.get("/library/reading?stream=science").json()]
    assert posted.json()["id"] not in [
        x["id"] for x in client.get("/library/reading?stream=commerce").json()]
    assert client.get("/library/reading?stream=bogus").status_code == 422


def test_doubt_ask_stores_asker_stream(client):
    headers, _ = register(client, "stream-asker@x.in", grade=11)
    r = client.post("/doubts", json={
        "subject_name": "Chemistry", "text": "Stream probe doubt about salts"},
        headers=headers)
    assert r.status_code == 201, r.text
    rows = client.get("/doubts", headers=headers).json()
    mine = [d for d in rows if d["text"].startswith("Stream probe")]
    assert mine and mine[0]["stream"] == "science"
    arts = [d for d in client.get("/doubts?stream=arts", headers=headers).json()
            if d["text"].startswith("Stream probe")]
    assert arts == []
    assert client.get("/doubts?stream=bogus", headers=headers).status_code == 422


def test_material_upload_derives_stream(client):
    teacher = login(client, "teacher1@gramshiksha.in")
    files = {"file": ("probe.pdf", b"%PDF-1.4 probe", "application/pdf")}
    r = client.post("/materials", data={
        "title": "Stream Probe Material", "type": "notes",
        "class_grade": 11, "board": BOARD, "subject_name": "Economics",
        "visibility": "public"}, files=files, headers=teacher)
    assert r.status_code == 201, r.text
    got = client.get("/materials?board=" + BOARD.replace(" ", "+"), headers=teacher).json()
    mine = [m for m in got if m["title"] == "Stream Probe Material"]
    assert mine and mine[0]["stream"] == "commerce"
    excl = client.get("/materials?board=" + BOARD.replace(" ", "+") + "&stream=science",
                      headers=teacher).json()
    assert all(m["title"] != "Stream Probe Material" for m in excl)
