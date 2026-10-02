"""Monthly Reading List: one teacher's pick, every student's book club.

Audience decision under test: the list is a *book club*, not an assignment —
GET /library/reading answers without a session and never filters by class, so
a Class 4 learner can follow a Class 10 teacher's pick.

Contract under test:
* only an **approved** teacher may post (anonymous 401, student 403, a fresh
  teacher signup still "pending" 403 — approval is what confers the power);
* re-posting the same title in the same month rewrites it instead of stacking
  a duplicate;
* the pick links to the catalog when its title already resolves there
  (`readable: true` → the UI's "Read now") and stays unlinked otherwise
  (`readable: false` → the UI's "Find this book", which queues the finder);
* an unknown textbook_id is refused rather than accepted as a dead "Read now";
* only the owner (or an admin) can withdraw a pick;
* the returned window is this month and the two before it, newest first — a
  pick from 2019 must not haunt the top of the list forever.

Every path is a bare string literal (or an f-string with a literal template)
because the route-coverage canary parses test source with `ast`.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect as sa_inspect
from sqlmodel import Session, select

from app.db import engine
from app.main import app
from app.models import ReadingPick, Textbook, User, utcnow

# Private board + fake PDF ids: probe rows are recognisably ours (so they can
# be cleaned up) and must never surface in /textbooks/coverage, which asserts
# exactly the three real boards.
BOARD = "Reading Test Board"
FAKE_PDF = "https://ebooks.ebalbharati.in/pdfs/99990040{}.pdf"
TITLE = "Reading Probe Book"
AUTO_TITLE = "Reading Auto Link Probe"
UNLINKED_TITLE = "Reading Probe Not In Library Yet"
ADMIN_EMAIL = "reading-admin@x.in"

PREFIXES = ("Reading Probe", "Reading Auto Link", "Reading Stale")


@pytest.fixture(name="client")
def client_fixture():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _probe_picks_do_not_outlive_their_test():
    """Picks first, then the probe books they point at: a dangling
    readingpick.textbook_id would break the next run's catalog probe."""
    yield
    if not sa_inspect(engine).has_table("readingpick"):
        return  # the app boots (and migrates) on the first TestClient use
    with Session(engine) as s:
        for r in s.exec(select(ReadingPick)).all():
            if str(r.title).startswith(PREFIXES):
                s.delete(r)
        for t in s.exec(select(Textbook).where(Textbook.board == BOARD)).all():
            s.delete(t)
        for u in s.exec(select(User).where(User.email == ADMIN_EMAIL)).all():
            s.delete(u)
        s.commit()


def now_month() -> str:
    now = utcnow()
    return f"{now.year:04d}-{now.month:02d}"


def next_month() -> str:
    now = utcnow()
    y, m = (now.year + 1, 1) if now.month == 12 else (now.year, now.month + 1)
    return f"{y:04d}-{m:02d}"


def login(client, email, password="Teach@1234"):
    r = client.post("/auth/token", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def register(client, email, role="student"):
    r = client.post("/auth/register", json={
        "email": email, "name": "Reading Probe", "password": "Reading@123",
        "role": role, "class_grade": 8, "board": "Maharashtra SSC"})
    assert r.status_code == 201, r.text
    body = r.json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body["id"]


def seed_book(title: str) -> int:
    """A healthy deep-linked catalog row on our private board."""
    with Session(engine) as s:
        row = Textbook(board=BOARD, class_grade=8, subject_name="Reading Probe",
                       lang="en", title=title,
                       source_url="https://books.ebalbharati.in/reading-probe",
                       deep_url=FAKE_PDF.format(1), last_ok=True)
        s.add(row)
        s.commit()
        return row.id


def admin_session(client):
    """An approved platform_admin: registration only ever hands out `teacher`,
    and approval is what confers privilege, so promote in the DB."""
    headers, uid = register(client, ADMIN_EMAIL, role="teacher")
    with Session(engine) as s:
        user = s.get(User, uid)
        user.role = "platform_admin"
        user.role_status = "active"
        s.add(user)
        s.commit()
    return headers


def test_reading_list_is_public_windowed_and_newest_first(client):
    teacher = login(client, "teacher1@gramshiksha.in")
    fresh = client.post("/library/reading", json={
        "month": now_month(), "title": TITLE, "note": "This month's pick"},
        headers=teacher).json()
    stale = client.post("/library/reading", json={
        "month": "2019-01", "title": f"{TITLE} Stale"},
        headers=teacher).json()

    # public: no session, no class filter — a book club anyone can walk into
    r = client.get("/library/reading")
    assert r.status_code == 200, r.text
    rows = r.json()
    mine = [x for x in rows if x["id"] in (fresh["id"], stale["id"])]
    assert [x["id"] for x in mine] == [fresh["id"]]      # the 2019 pick is gone
    assert mine[0]["teacher_name"]                        # resolved, not raw id
    assert mine[0]["readable"] is False and mine[0]["textbook_id"] is None

    # newest month first, and a shape the frontend can bind without guessing
    list_keys = {"id", "month", "title", "author", "note", "lang",
                 "subject_name", "class_grade", "board", "textbook_id",
                 "readable", "teacher_name", "created_at"}
    assert all(set(x) == list_keys for x in rows)
    months = [x["month"] for x in rows]
    assert months == sorted(months, reverse=True)
    # a POST answer carries the same shape plus the created flag
    assert set(fresh) == list_keys | {"created"}
    # the owner's management view needs a session and narrows to their picks
    assert client.get("/library/reading?mine=1").status_code == 401
    own = client.get("/library/reading?mine=1", headers=teacher).json()
    assert {x["id"] for x in own} == {fresh["id"]}          # 2019 is out of window
    assert {x["id"] for x in client.get(
        "/library/reading?mine=1", headers=login(client, "teacher2@gramshiksha.in")).json()} == set()
    # production mount twin
    assert client.get("/api/library/reading").status_code == 200


def test_teacher_picks_a_readable_book_and_a_repost_updates_it(client):
    teacher = login(client, "teacher1@gramshiksha.in")
    book_id = seed_book(TITLE)

    created = client.post("/library/reading", json={
        "month": now_month(), "title": TITLE, "author": "Probe Author",
        "note": "Read the first chapter", "lang": "en",
        "subject_name": "Reading Probe", "textbook_id": book_id},
        headers=teacher)
    assert created.status_code == 200, created.text
    pick = created.json()
    assert pick["created"] is True and pick["readable"] is True
    assert pick["textbook_id"] == book_id and pick["teacher_name"]

    # same title, same month → the note is rewritten, no duplicate row
    repost = client.post("/library/reading", json={
        "month": now_month(), "title": "  reading probe   BOOK ",
        "note": "Two chapters instead"}, headers=teacher)
    assert repost.status_code == 200, repost.text
    upd = repost.json()
    assert upd["created"] is False and upd["id"] == pick["id"]
    assert upd["note"] == "Two chapters instead"
    # …and the edit keeps the "Read now" link it already had
    assert upd["textbook_id"] == book_id and upd["readable"] is True

    with Session(engine) as s:
        teacher_row = s.exec(select(User).where(
            User.email == "teacher1@gramshiksha.in")).one()
        n = len(s.exec(select(ReadingPick).where(
            ReadingPick.month == now_month(),
            ReadingPick.teacher_id == teacher_row.id,
            ReadingPick.title.like("Reading Probe%"))).all())
    assert n == 1                                      # one row, not two


def test_only_an_approved_teacher_may_post(client):
    payload = {"month": now_month(), "title": f"{TITLE} Gate"}
    # nobody signed in
    assert client.post("/library/reading", json=payload).status_code == 401
    # a student
    student, _ = register(client, "reading-student@x.in")
    assert client.post("/library/reading", json=payload,
                       headers=student).status_code == 403
    # a teacher who has not been approved yet — approval is the real gate
    pending, _ = register(client, "reading-pending-teacher@x.in",
                          role="teacher")
    refused = client.post("/library/reading", json=payload, headers=pending)
    assert refused.status_code == 403
    assert "pending" in str(refused.json()["detail"]).lower()


def test_auto_links_books_the_library_already_has(client):
    teacher = login(client, "teacher1@gramshiksha.in")

    # an unknown textbook is never accepted as a dead "Read now"
    assert client.post("/library/reading", json={
        "month": now_month(), "title": f"{TITLE} Unknown",
        "textbook_id": 99999999}, headers=teacher).status_code == 422
    # a bad month is rejected before anything is written
    assert client.post("/library/reading", json={
        "month": "2026-13", "title": f"{TITLE} Bad Month"},
        headers=teacher).status_code == 422

    book_id = seed_book(AUTO_TITLE)
    linked = client.post("/library/reading", json={
        "month": now_month(), "title": AUTO_TITLE, "note": "auto-link"},
        headers=teacher).json()
    assert linked["textbook_id"] == book_id and linked["readable"] is True

    unlinked = client.post("/library/reading", json={
        "month": now_month(), "title": UNLINKED_TITLE},
        headers=teacher).json()
    assert unlinked["textbook_id"] is None
    assert unlinked["readable"] is False        # → the UI offers "Find this book"


def test_delete_is_the_owner_or_an_admin_alone(client):
    teacher = login(client, "teacher1@gramshiksha.in")
    other = login(client, "teacher2@gramshiksha.in")
    pick = client.post("/library/reading", json={
        "month": now_month(), "title": f"{TITLE} Owned"}, headers=teacher).json()

    assert client.delete(f"/library/reading/{pick['id']}").status_code == 401
    assert client.delete(f"/library/reading/{pick['id']}",
                         headers=other).status_code == 403
    assert client.delete("/library/reading/99999999",
                         headers=teacher).status_code == 404

    # an admin withdraws someone else's pick (the platform must be able to)
    admin = admin_session(client)
    assert client.delete(f"/library/reading/{pick['id']}",
                         headers=admin).status_code == 200

    # …and the owner still can, on their own pick
    own = client.post("/library/reading", json={
        "month": now_month(), "title": f"{TITLE} Mine"}, headers=teacher).json()
    assert client.delete(f"/library/reading/{own['id']}",
                         headers=teacher).status_code == 200
    assert not any(x["id"] == own["id"]
                   for x in client.get("/library/reading").json())


def test_admin_inherits_teacher_powers_but_not_a_learners_seat(client):
    """`require_roles` promises "admins inherit teacher powers", and the
    teacher dashboard renders the pick form for a platform admin — so POST
    has to accept it (a regression the live probe hit: the form was there,
    the API answered 403 "Requires role: teacher"). The inheritance is
    one-way: a student-only route must still refuse them.
    """
    admin = admin_session(client)
    posted = client.post("/library/reading", json={
        "month": now_month(), "title": f"{TITLE} Admin Pick"}, headers=admin)
    assert posted.status_code == 200, posted.text
    assert client.delete(f"/library/reading/{posted.json()['id']}",
                         headers=admin).status_code == 200
    # learner-only territory stays shut for admins …
    assert client.get("/progress/summary", headers=admin).status_code == 403
    # … while teacher territory (create a lesson) is theirs to use
    assert client.post("/lessons", json={"chapter_id": 999999, "title_en": "a",
                                         "title_hi": "b", "title_mr": "c"},
                       headers=admin).status_code == 404


def test_a_pick_for_next_month_is_visible_immediately(client):
    """The server clock is UTC and the audience is IST (UTC+5:30), so between
    00:00 and 05:30 on the 1st "this month" is still last month upstream — and
    a teacher pre-posting next month's pick is normal. Either way the pick the
    teacher just published must be on the list at once, not hours later."""
    teacher = login(client, "teacher1@gramshiksha.in")
    posted = client.post("/library/reading", json={
        "month": next_month(), "title": f"{TITLE} Next Month"}, headers=teacher)
    assert posted.status_code == 200, posted.text
    assert posted.json()["id"] in [
        x["id"] for x in client.get("/library/reading").json()]
