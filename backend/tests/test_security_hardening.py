"""Regression tests for the 2026-10-20 security audit fixes.

Each test pins one finding so it cannot silently come back:

  * H1 — a self-service account cannot publish material without moderation
  * M2 — an unpublished lesson cannot be attempted/graded
  * M3 — search never returns another school's private material
  * M4 — quiz retakes do not farm XP
  * M7 — parent invites do not reveal whether an email has an account
  * M8/L1/L2 — authenticated responses are private, request ids are sanitized
  * L14 — a renamed HTML file cannot masquerade as a PDF
"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db import engine
from app.main import app
from app.models import Lesson, Material, Quiz, User

PDF = b"%PDF-1.4 fake content"
PASSWORD = "Original@123"


@pytest.fixture(name="client")
def client_fixture():
    with TestClient(app) as c:
        yield c


def login(client, email, password=PASSWORD):
    r = client.post("/auth/token", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def signup(client, email, role="student", name="Audit Probe", school_name=""):
    payload = {"email": email, "name": name, "password": PASSWORD, "role": role}
    if role == "student":
        payload.update({"class_grade": 8, "board": "Maharashtra SSC"})
    if school_name:
        payload["school_name"] = school_name
    r = client.post("/auth/register", json=payload)
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, r.json()["id"]


def upload(client, headers, title="Audit file", visibility="public",
           file=("a.pdf", PDF, "application/pdf")):
    return client.post("/materials", data={
        "title": title, "type": "notes", "class_grade": 8,
        "board": "Maharashtra SSC", "subject_name": "Science", "lang": "en",
        "visibility": visibility, "source_of_content": "audit fixture"},
        files={"file": file}, headers=headers)


def first_lesson_id(client):
    courses = client.get("/courses", params={"class_grade": 8,
                                             "board": "Maharashtra SSC"}).json()
    for c in courses["items"]:
        detail = client.get(f"/courses/{c['id']}").json()
        for ch in detail["chapters"]:
            if ch["lessons"]:
                return ch["lessons"][0]["id"]
    raise AssertionError("seed has no lesson attached to a chapter")


# ---------- H1 ----------

def test_parent_upload_starts_pending_and_is_not_public(client):
    parent, _ = signup(client, "audit-parent@x.in", role="parent")
    r = upload(client, parent, title="Parent-published note")
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "pending"

    with Session(engine) as s:
        row = s.get(Material, r.json()["id"])
        assert row is not None and row.status == "pending"

    titles = [m["title"] for m in client.get("/materials").json()]
    assert "Parent-published note" not in titles


def test_approved_teacher_still_publishes_immediately(client):
    teacher = login(client, "teacher1@gramshiksha.in", "Teach@1234")
    r = upload(client, teacher, title="Teacher-published note")
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "approved"


# ---------- M2 ----------

def test_unpublished_lesson_cannot_be_attempted(client):
    lesson_id = first_lesson_id(client)
    with Session(engine) as s:
        lesson = s.get(Lesson, lesson_id)
        assert lesson is not None
        lesson.published = False
        s.add(lesson)
        s.commit()
    try:
        student, _ = signup(client, "audit-draft@x.in")
        r = client.post(f"/lessons/{lesson_id}/attempt",
                        json={"answers": [{"question_id": 0, "answer": ""}], "minutes": 0},
                        headers=student)
        assert r.status_code == 404, r.text
        assert client.get(f"/learn/lessons/{lesson_id}", headers=student).status_code == 404
    finally:
        with Session(engine) as s:
            lesson = s.get(Lesson, lesson_id)
            if lesson is not None:
                lesson.published = True
                s.add(lesson)
                s.commit()


# ---------- M3 ----------

def test_search_does_not_leak_another_schools_private_material(client):
    teacher_a = login(client, "teacher1@gramshiksha.in", "Teach@1234")
    r = upload(client, teacher_a, title="CrossSchoolPrivateAudit", visibility="private")
    assert r.status_code == 201, r.text
    r = upload(client, teacher_a, title="CrossSchoolPublicAudit", visibility="public")
    assert r.status_code == 201, r.text

    outsider, _ = signup(client, "audit-outsider@x.in")
    found = client.get("/search", params={"q": "CrossSchool"}, headers=outsider).json()
    titles = [m["title"] for m in found["materials"]]
    assert "CrossSchoolPublicAudit" in titles
    assert "CrossSchoolPrivateAudit" not in titles


# ---------- M4 ----------

def test_quiz_retake_does_not_farm_xp(client):
    student, student_id = signup(client, "audit-quiz@x.in")
    with Session(engine) as s:
        quiz = s.exec(select(Quiz)).all()
        quiz_id = None
        for q in quiz:
            if q.lesson_id is None:
                quiz_id = q.id
                break
            lesson = s.get(Lesson, q.lesson_id)
            if lesson is not None and lesson.published:
                quiz_id = q.id
                break
    assert quiz_id is not None, "seed has no published quiz"

    payload = {"answers": [{"question_id": 999999, "answer": None}], "time_taken_s": 1}
    assert client.post(f"/learn/quizzes/{quiz_id}/submit", json=payload,
                       headers=student).status_code == 200
    with Session(engine) as s:
        xp_after_first = s.get(User, student_id).xp
    assert client.post(f"/learn/quizzes/{quiz_id}/submit", json=payload,
                       headers=student).status_code == 200
    with Session(engine) as s:
        assert s.get(User, student_id).xp == xp_after_first


# ---------- M7 ----------

def test_parent_invite_does_not_reveal_whether_an_account_exists(client):
    student, _ = signup(client, "audit-invite@x.in")
    unknown = client.post("/parent/invite", json={"parent_email": "nobody-here@x.in"},
                          headers=student)
    known = client.post("/parent/invite",
                        json={"parent_email": "teacher1@gramshiksha.in"},
                        headers=student)
    assert unknown.status_code == known.status_code == 200
    assert set(unknown.json()) == set(known.json()) == {"invite", "expires_in_seconds"}


# ---------- M8 / L1 ----------

def test_authenticated_responses_are_private(client):
    student, _ = signup(client, "audit-cache@x.in")
    me = client.get("/auth/me", headers=student)
    assert me.headers["Cache-Control"] == "no-store"
    assert "Authorization" in me.headers.get("Vary", "")

    summary = client.get("/progress/summary", headers=student)
    assert summary.headers["Cache-Control"].startswith("private")

    public = client.get("/courses")
    assert "private" not in public.headers.get("Cache-Control", "")


def test_request_id_is_sanitized(client):
    long_id = "a" * 200
    r = client.get("/health", headers={"X-Request-ID": long_id})
    assert r.headers["X-Request-ID"] != long_id
    assert len(r.headers["X-Request-ID"]) <= 64

    r = client.get("/health", headers={"X-Request-ID": "probe-123_ok"})
    assert r.headers["X-Request-ID"] == "probe-123_ok"


# ---------- H3 ----------

def test_rate_limit_key_uses_the_last_forwarded_hop():
    """A spoofed leading XFF entry must not become the bucket key."""
    from starlette.requests import Request

    from app.ratelimit import _client_ip

    def make(xff: str) -> Request:
        return Request({"type": "http", "headers": [(b"x-forwarded-for", xff.encode())],
                        "client": ("10.0.0.2", 1234)})

    assert _client_ip(make("1.2.3.4, 203.0.113.9")) == "203.0.113.9"
    assert _client_ip(make("not-an-ip")) == "10.0.0.2"


def test_login_locks_per_account_not_only_per_ip(client):
    """Rotating the client IP must not buy unlimited password guesses against
    one address — the account itself is locked after ten failures."""
    bad = {"username": "teacher1@gramshiksha.in", "password": "definitely-wrong"}
    for _ in range(10):
        assert client.post("/auth/token", data=bad,
                           headers={"X-Forwarded-For": "10.0.0.1"}).status_code == 401
    r = client.post("/auth/token", data=bad, headers={"X-Forwarded-For": "10.0.0.99"})
    assert r.status_code == 429
    assert int(r.headers.get("Retry-After", "0")) > 0

    # Correct credentials are refused while the lock is active (that is the
    # point), and the lock is per-account, not global.
    assert client.post("/auth/token", data={
        "username": "teacher1@gramshiksha.in", "password": "Teach@1234"}).status_code == 429
    assert client.post("/auth/token", data={
        "username": "admin@gramshiksha.in", "password": "Admin@1234"}).status_code == 200


# ---------- L14 ----------

def test_renamed_html_is_not_accepted_as_a_pdf(client):
    student, _ = signup(client, "audit-magic@x.in")
    r = upload(client, student, title="Not really a PDF",
               file=("a.pdf", b"<html><script>alert(1)</script></html>", "application/pdf"))
    assert r.status_code == 422
    assert "does not look like" in r.json()["detail"]
