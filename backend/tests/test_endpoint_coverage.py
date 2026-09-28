"""Coverage for the routes no other suite ever reached.

The audit counted 63 logical endpoints but only 42 were exercised anywhere.
This file closes the remaining 21:

  PATCH /auth/me
  GET   /learn/lessons/{id}        GET /learn/quizzes/{id}      POST /learn/sync
  DELETE /materials/{id}
  POST/GET/DELETE /bookmarks
  POST/GET/PATCH/DELETE /notes
  GET   /notifications             POST /notifications/read-all
  GET   /progress/summary          GET /progress/weekly
  GET   /teacher/overview          POST /parent/link
  GET   /school/stats              POST /school/announce
  GET   /admin/reports

A few are also re-checked through their `/api/...` twin, which is the mount a
production deployment actually serves (the bare paths exist for the dev proxy).

Nearly every test registers its own throwaway account instead of reusing the
seeded ones: the database is shared by the whole pytest process, so mutating a
seeded row here would show up as a mysterious failure in another file.
"""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app

PDF = b"%PDF-1.4 fake content"


@pytest.fixture(name="client")
def client_fixture():
    with TestClient(app) as c:
        yield c


def login(client, email, password):
    r = client.post("/auth/token", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def signup(client, email, role="student", name="Probe User",
           grade=8, board="Maharashtra SSC", school_name=""):
    """Register a fresh account and return (auth headers, user id)."""
    payload = {"email": email, "name": name, "password": "Original@123", "role": role}
    if role == "student":
        payload.update({"class_grade": grade, "board": board})
    if school_name:
        payload["school_name"] = school_name
    r = client.post("/auth/register", json=payload)
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, r.json()["id"]


def upload(client, headers, title="Probe file", visibility="public"):
    r = client.post("/materials", data={
        "title": title, "type": "notes", "class_grade": 8,
        "board": "Maharashtra SSC", "subject_name": "Science", "lang": "en",
        "visibility": visibility, "source_of_content": "test fixture"},
        files={"file": ("a.pdf", PDF, "application/pdf")}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def first_lesson_and_chapter(client):
    """Pull a real lesson id and chapter id out of the seeded catalog."""
    courses = client.get("/courses", params={"class_grade": 8, "board": "Maharashtra SSC"}).json()
    for c in courses["items"]:
        detail = client.get(f"/courses/{c['id']}").json()
        for ch in detail["chapters"]:
            if ch["lessons"]:
                return ch["lessons"][0]["id"], ch["id"]
    raise AssertionError("seed has no lesson attached to a chapter")


# ---------- auth ----------

def test_update_profile(client):
    h, _ = signup(client, "profile@x.in", name="Before Name")

    r = client.patch("/auth/me", json={
        "name": "After Name", "lang_pref": "mr", "class_grade": 9,
        "board": "CBSE", "school_name": "Sunrise High"}, headers=h)
    assert r.status_code == 200 and r.json()["ok"]

    me = client.get("/auth/me", headers=h).json()
    assert me["name"] == "After Name"
    assert me["lang_pref"] == "mr"
    assert me["class_grade"] == 9 and me["board"] == "CBSE"
    # school_name looks the school up (creating it when new) and links it.
    assert me["school_id"]

    # Re-sending the same school name reuses the row instead of forking a new one.
    school_id = me["school_id"]
    assert client.patch("/auth/me", json={"school_name": "Sunrise High"},
                        headers=h).status_code == 200
    assert client.get("/auth/me", headers=h).json()["school_id"] == school_id

    # Bad language code is rejected rather than stored.
    assert client.patch("/auth/me", json={"lang_pref": "de"}, headers=h).status_code == 422
    # Out-of-range grade is rejected by the schema.
    assert client.patch("/auth/me", json={"class_grade": 99}, headers=h).status_code == 422
    # Anonymous callers get nothing.
    assert client.patch("/auth/me", json={"name": "x"}).status_code == 401


# ---------- learn ----------

def test_lesson_detail(client):
    h, _ = signup(client, "lessonview@x.in")
    lesson_id, _ = first_lesson_and_chapter(client)

    r = client.get(f"/learn/lessons/{lesson_id}", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == lesson_id
    assert body["title"] and body["body"]
    assert body["duration_min"] > 0 and body["estimate_mb"] >= 0
    assert body["completed"] is False
    assert body["course_title"] and body["chapter_title"]
    # Grading material stays hidden on a plain GET.
    assert all(q["correct"] is None and q["explanation"] is None for q in body["questions"])

    # Language selection really swaps the trilingual content.
    mr = client.get(f"/learn/lessons/{lesson_id}", params={"lang": "mr"}, headers=h).json()
    assert mr["title"] != body["title"] and mr["body"] != body["body"]

    assert client.get("/learn/lessons/999999", headers=h).status_code == 404
    assert client.get(f"/learn/lessons/{lesson_id}").status_code == 401


def test_quiz_detail(client):
    h, _ = signup(client, "quizview@x.in")
    _, chapter_id = first_lesson_and_chapter(client)

    quiz = client.get(f"/learn/quizzes-by-chapter/{chapter_id}", headers=h)
    assert quiz.status_code == 200, quiz.text
    quiz_id = quiz.json()["id"]

    r = client.get(f"/learn/quizzes/{quiz_id}", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == quiz_id and body["title"]
    assert body["time_limit_min"] > 0
    assert body["questions"], "seeded chapter quizzes must carry questions"
    assert all(q["correct"] is None for q in body["questions"])

    # The production /api mount serves the same document.
    twin = client.get(f"/api/learn/quizzes/{quiz_id}", headers=h)
    assert twin.status_code == 200
    assert twin.json()["id"] == body["id"]
    assert len(twin.json()["questions"]) == len(body["questions"])

    assert client.get("/learn/quizzes/999999", headers=h).status_code == 404
    assert client.get(f"/learn/quizzes/{quiz_id}").status_code == 401


def test_offline_sync_replays_the_queue(client):
    h, _ = signup(client, "syncer@x.in")
    lesson_id, _ = first_lesson_and_chapter(client)
    practice = client.get("/learn/practice/questions",
                          params={"subject_name": "Mathematics", "limit": 1}, headers=h).json()
    assert practice, "question bank should answer a practice request"

    items = [
        {"kind": "lesson_complete", "lesson_id": lesson_id, "payload": {"minutes": 7}},
        {"kind": "practice_answer", "question_id": practice[0]["id"],
         "payload": {"answer": 0, "minutes": 2}},
        {"kind": "something_else", "payload": {}},
    ]
    r = client.post("/learn/sync", json=items, headers=h)
    assert r.status_code == 200, r.text
    results = r.json()["synced"]
    assert [x["ok"] for x in results] == [True, True, False]
    assert results[2]["error"] == "unsupported"

    # The replayed work actually landed: lesson done, lesson count on the dashboard.
    summary = client.get("/progress/summary", headers=h).json()
    assert summary["lessons_completed"] == 1

    # A missing lesson id reports the failure instead of exploding.
    bad = client.post("/learn/sync", json=[
        {"kind": "lesson_complete", "lesson_id": 999999, "payload": {}}], headers=h)
    assert bad.status_code == 200
    assert bad.json()["synced"][0] == {"ok": False, "error": "Lesson not found"}

    # Queues are per-student: teachers cannot replay one.
    t = login(client, "teacher1@gramshiksha.in", "Teach@1234")
    assert client.post("/learn/sync", json=items, headers=t).status_code == 403
    assert client.post("/learn/sync", json=items).status_code == 401


# ---------- materials ----------

def test_delete_material_permissions(client):
    owner, _ = signup(client, "owner@x.in")
    stranger, _ = signup(client, "stranger@x.in")
    teacher = login(client, "teacher1@gramshiksha.in", "Teach@1234")

    mid = upload(client, owner, title="Owned handout")

    # Ownership decides: not the uploader, not a moderator -> refused.
    assert client.delete(f"/materials/{mid}", headers=stranger).status_code == 403
    assert client.delete(f"/materials/{mid}").status_code == 401

    # The owner can remove it, and the row really goes away.
    assert client.delete(f"/materials/{mid}", headers=owner).status_code == 200
    assert client.delete(f"/materials/{mid}", headers=owner).status_code == 404
    assert client.get(f"/materials/{mid}/download", headers=owner).status_code == 404

    # Moderators can pull material off the platform.
    mid2 = upload(client, owner, title="Reportable handout")
    assert client.delete(f"/materials/{mid2}", headers=teacher).status_code == 200
    assert client.delete("/materials/999999", headers=teacher).status_code == 404


# ---------- bookmarks ----------

def test_bookmarks_crud(client):
    a, _ = signup(client, "book-a@x.in")
    b, _ = signup(client, "book-b@x.in")
    lesson_id, _ = first_lesson_and_chapter(client)
    course_id = client.get("/courses", params={"class_grade": 8}).json()["items"][0]["id"]

    # A bookmark must point at something.
    assert client.post("/bookmarks", headers=a).status_code == 422
    assert client.post("/bookmarks").status_code == 401

    assert client.post("/bookmarks", params={"lesson_id": lesson_id}, headers=a).status_code == 201
    assert client.post("/bookmarks", params={"course_id": course_id}, headers=a).status_code == 201

    mine = client.get("/bookmarks", headers=a).json()
    assert [(m["lesson_id"], m["course_id"]) for m in mine] == [(lesson_id, None), (None, course_id)]
    assert client.get("/bookmarks", headers=b).json() == []
    assert client.get("/api/bookmarks", headers=a).json() == mine   # production mount

    # Someone else's bookmark looks exactly like a missing one.
    target = mine[0]["id"]
    assert client.delete(f"/bookmarks/{target}", headers=b).status_code == 404
    assert client.delete(f"/bookmarks/{target}").status_code == 401
    assert client.delete(f"/bookmarks/{target}", headers=a).status_code == 200
    assert client.delete(f"/bookmarks/{target}", headers=a).status_code == 404
    assert len(client.get("/bookmarks", headers=a).json()) == 1


# ---------- notes ----------

def test_notes_crud(client):
    a, _ = signup(client, "note-a@x.in")
    b, _ = signup(client, "note-b@x.in")
    lesson_id, _ = first_lesson_and_chapter(client)

    r = client.post("/notes", json={"lesson_id": lesson_id, "body": "Cell wall is rigid"}, headers=a)
    assert r.status_code == 201, r.text
    note_id = r.json()["id"]

    assert [n["id"] for n in client.get("/notes", headers=a).json()] == [note_id]
    assert len(client.get("/notes", params={"lesson_id": lesson_id}, headers=a).json()) == 1
    assert client.get("/notes", headers=b).json() == []
    assert client.get("/api/notes", headers=a).json()[0]["body"] == "Cell wall is rigid"

    # The edit body is a full NoteIn — lesson_id is mandatory by the model.
    assert client.patch(f"/notes/{note_id}", json={"body": "x"}, headers=a).status_code == 422

    r = client.patch(f"/notes/{note_id}",
                     json={"lesson_id": lesson_id, "body": "Updated note"}, headers=a)
    assert r.status_code == 200 and r.json()["ok"]
    assert client.get("/notes", headers=a).json()[0]["body"] == "Updated note"

    # Ownership is enforced on edit and delete alike.
    hijack = {"lesson_id": lesson_id, "body": "Hijacked"}
    assert client.patch(f"/notes/{note_id}", json=hijack, headers=b).status_code == 404
    assert client.delete(f"/notes/{note_id}", headers=b).status_code == 404
    assert client.delete(f"/notes/{note_id}", headers=a).status_code == 200
    assert client.delete(f"/notes/{note_id}", headers=a).status_code == 404
    assert client.post("/notes", json={"lesson_id": lesson_id, "body": "x"}).status_code == 401


# ---------- notifications ----------

def test_notifications_and_school_announcement(client):
    student, _ = signup(client, "notify@x.in")
    school_admin = login(client, "school@gramshiksha.in", "School@1234")
    platform_admin = login(client, "admin@gramshiksha.in", "Admin@1234")

    assert client.get("/notifications", headers=student).status_code == 200
    assert client.get("/notifications").status_code == 401

    # Announcing is an admin-only action.
    assert client.post("/school/announce", params={"title": "Holiday"},
                       headers=student).status_code == 403

    r = client.post("/school/announce",
                    params={"title": "Holiday tomorrow", "body": "School closed"},
                    headers=school_admin)
    assert r.status_code == 200 and r.json()["notified"] >= 1

    notes = client.get("/notifications", headers=student).json()
    mine = [n for n in notes if n["type"] == "announcement"]
    assert mine, "announcement should reach every student"
    assert mine[0]["payload"] == {"title": "Holiday tomorrow", "body": "School closed"}
    assert mine[0]["read"] is False

    # read-all flips only this user's unread rows and reports the count.
    r = client.post("/notifications/read-all", headers=student)
    assert r.status_code == 200 and r.json()["marked"] >= 1
    assert all(n["read"] for n in client.get("/notifications", headers=student).json())
    # Running it again finds nothing to do.
    assert client.post("/notifications/read-all", headers=student).json()["marked"] == 0

    # Platform admins can announce too.
    r = client.post("/school/announce", params={"title": "Exam timetable"}, headers=platform_admin)
    assert r.status_code == 200
    assert client.post("/notifications/read-all").status_code == 401


# ---------- student progress dashboards ----------

def test_progress_summary_and_weekly(client):
    student = login(client, "student1@gramshiksha.in", "Learn@1234")
    teacher = login(client, "teacher1@gramshiksha.in", "Teach@1234")

    r = client.get("/progress/summary", headers=student)
    assert r.status_code == 200, r.text
    body = r.json()
    for key in ("lessons_completed", "quizzes_taken", "quiz_avg_pct", "week_minutes",
                "week_lessons", "week_quizzes", "xp", "streak_days", "badges", "certificates"):
        assert key in body, key
    assert isinstance(body["badges"], list) and isinstance(body["certificates"], list)
    assert client.get("/api/progress/summary", headers=student).status_code == 200

    r = client.get("/progress/weekly", headers=student)
    assert r.status_code == 200, r.text
    days = r.json()
    assert len(days) == 14 and set(days[0]) == {"date", "minutes"}
    assert days[-1]["date"] == date.today().isoformat()
    assert days[-1]["minutes"] >= 0

    # Student dashboards are student-only.
    assert client.get("/progress/summary", headers=teacher).status_code == 403
    assert client.get("/progress/weekly", headers=teacher).status_code == 403
    assert client.get("/progress/summary").status_code == 401


# ---------- teacher ----------

def test_teacher_overview(client):
    teacher = login(client, "teacher1@gramshiksha.in", "Teach@1234")
    student = login(client, "student1@gramshiksha.in", "Learn@1234")

    r = client.get("/teacher/overview", headers=teacher)
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"my_courses", "pending_material_reviews",
                         "pending_doubts", "total_students"}
    assert isinstance(body["my_courses"], list)
    assert body["total_students"] >= 1
    assert isinstance(body["pending_material_reviews"], int)

    assert client.get("/teacher/overview", headers=student).status_code == 403
    assert client.get("/teacher/overview").status_code == 401


# ---------- parent ----------

def test_parent_link_flow(client):
    parent, _ = signup(client, "link-parent@x.in", role="parent", name="Linking Parent")
    child, child_id = signup(client, "link-child@x.in", name="Linked Kid", grade=7)
    teacher = login(client, "teacher1@gramshiksha.in", "Teach@1234")

    assert client.get("/parent/children", headers=parent).json() == []

    r = client.post("/parent/link", params={"child_email": "link-child@x.in"}, headers=parent)
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True, "child": "Linked Kid"}

    kids = client.get("/parent/children", headers=parent).json()
    assert [k["id"] for k in kids] == [child_id]
    assert kids[0]["lessons_completed"] >= 0 and "weak_subjects" in kids[0]

    # Unknown address, a non-student address, and a missing parameter all fail
    # the same way a typo should.
    assert client.post("/parent/link", params={"child_email": "nobody@x.in"},
                       headers=parent).status_code == 404
    assert client.post("/parent/link", params={"child_email": "teacher1@gramshiksha.in"},
                       headers=parent).status_code == 404
    assert client.post("/parent/link", headers=parent).status_code == 422

    # Only parents may link.
    assert client.post("/parent/link", params={"child_email": "link-parent@x.in"},
                       headers=child).status_code == 403
    assert client.post("/parent/link", params={"child_email": "link-child@x.in"},
                       headers=teacher).status_code == 403
    assert client.post("/parent/link", params={"child_email": "link-child@x.in"}).status_code == 401


# ---------- school admin ----------

def test_school_stats(client):
    school_admin = login(client, "school@gramshiksha.in", "School@1234")
    platform_admin = login(client, "admin@gramshiksha.in", "Admin@1234")
    student = login(client, "student1@gramshiksha.in", "Learn@1234")

    r = client.get("/school/stats", headers=school_admin)
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"students", "teachers", "lessons_completed_total"}
    assert body["students"] >= 1 and body["teachers"] >= 1
    assert isinstance(body["lessons_completed_total"], int)

    assert client.get("/school/stats", headers=platform_admin).status_code == 200
    assert client.get("/school/stats", headers=student).status_code == 403
    assert client.get("/school/stats").status_code == 401


# ---------- moderation reports ----------

def test_admin_reports_lists_material_reports(client):
    teacher = login(client, "teacher1@gramshiksha.in", "Teach@1234")
    platform_admin = login(client, "admin@gramshiksha.in", "Admin@1234")
    reporter, _ = signup(client, "reporter@x.in")

    # Teacher uploads are auto-approved, so any student can see and report them.
    mid = upload(client, teacher, title="Reported handout")
    r = client.post(f"/materials/{mid}/report",
                    data={"reason": "incorrect", "detail": "Wrong formula on page 2"},
                    headers=reporter)
    assert r.status_code == 201, r.text

    r = client.get("/admin/reports", headers=platform_admin)
    assert r.status_code == 200, r.text
    hit = [x for x in r.json() if x["material_id"] == mid]
    assert hit, "the report we just filed should be listed"
    assert hit[0]["material_title"] == "Reported handout"
    assert hit[0]["reason"] == "incorrect"
    assert hit[0]["detail"] == "Wrong formula on page 2"
    assert hit[0]["created_at"]

    # Teachers and school admins share the queue; students do not.
    assert client.get("/admin/reports", headers=teacher).status_code == 200
    assert client.get("/admin/reports",
                      headers=login(client, "school@gramshiksha.in", "School@1234")).status_code == 200
    assert client.get("/admin/reports", headers=reporter).status_code == 403
    assert client.get("/admin/reports").status_code == 401
