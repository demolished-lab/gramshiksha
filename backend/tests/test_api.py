import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(name="client")
def client_fixture():
    # conftest.py points DATABASE_URL at a fresh temp SQLite file;
    # startup creates tables and seeds. No dependency override needed.
    with TestClient(app) as c:
        yield c


def login(client, email, password):
    r = client.post("/auth/token", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_register_login_me(client):
    r = client.post("/auth/register", json={
        "email": "newstu@x.in", "name": "N", "password": "Passw0rd@1",
        "role": "student", "lang_pref": "mr", "class_grade": 6, "board": "CBSE"})
    assert r.status_code == 201, r.text
    tok = r.json()["access_token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {tok}"}).json()
    assert me["role"] == "student" and me["class_grade"] == 6


def test_register_rejects_admin_role(client):
    r = client.post("/auth/register", json={
        "email": "hack@x.in", "name": "H", "password": "Passw0rd@1", "role": "platform_admin"})
    assert r.status_code == 422


def test_meta_and_courses(client):
    boards = client.get("/meta/boards").json()
    assert len(boards) >= 3
    subjects = client.get("/meta/subjects", params={"class_grade": 8, "board": "Maharashtra SSC"}).json()
    assert any(s["name_en"] == "Science" for s in subjects)
    courses = client.get("/courses", params={"class_grade": 8}).json()
    assert courses["total"] >= 2
    detail = client.get(f"/courses/{courses['items'][0]['id']}").json()
    assert detail["chapters"] and detail["chapters"][0]["lessons"]


def test_empty_course_filter_returns_zero_total(client):
    for path in ("/courses", "/api/courses"):
        response = client.get(path, params={"board": "No Such Board"})
        assert response.status_code == 200, response.text
        assert response.json() == {"total": 0, "items": []}


def test_enroll_and_progress_flow(client):
    h = login(client, "student2@gramshiksha.in", "Learn@1234")
    courses = client.get("/courses", params={"class_grade": 10, "board": "CBSE"}).json()
    cid = courses["items"][0]["id"]
    r = client.post(f"/courses/{cid}/enroll", headers=h)
    assert r.status_code == 201
    detail = client.get(f"/courses/{cid}").json()
    lesson_id = detail["chapters"][0]["lessons"][0]["id"]
    r = client.post(f"/learn/lessons/{lesson_id}/complete", params={"minutes": 12}, headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["xp"] > 0 and body["streak_days"] >= 1
    # progress reflects in enrollment
    mine = client.get("/my/courses", headers=h).json()
    assert any(c["id"] == cid and c["progress_pct"] > 0 for c in mine)


def test_quiz_submit_grades(client):
    h = login(client, "student1@gramshiksha.in", "Learn@1234")
    quiz = None
    # find any quiz via course detail
    courses = client.get("/courses", params={"class_grade": 8, "board": "Maharashtra SSC"}).json()
    for c in courses["items"]:
        d = client.get(f"/courses/{c['id']}").json()
        for ch in d["chapters"]:
            r = client.get(f"/learn/quizzes-by-chapter/{ch['id']}", headers=h)
            if r.status_code == 200:
                quiz = r.json()
                break
        if quiz:
            break
    assert quiz, "no quiz found in seed"
    answers = []
    for q in quiz["questions"]:
        answers.append({"question_id": q["id"], "answer": 0})
    r = client.post(f"/learn/quizzes/{quiz['id']}/submit", json={"answers": answers, "time_taken_s": 300}, headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["percentage"] >= 0 and len(body["per_question"]) == len(quiz["questions"])
    assert body["per_question"][0]["correct_answer"] is not None  # answers revealed after submit


def test_practice_and_weak_topics(client):
    h = login(client, "student1@gramshiksha.in", "Learn@1234")
    qs = client.get("/learn/practice/questions", params={"subject_name": "Mathematics", "limit": 5}, headers=h).json()
    assert qs
    # answer wrong repeatedly to trigger weak topic
    qid = qs[0]["id"]
    for _ in range(6):
        client.post("/learn/practice/answer", json={"question_id": qid, "answer": 0}, headers=h)
    weak = client.get("/learn/weak-topics", headers=h).json()
    assert isinstance(weak["weak"], list)


def test_learning_path_and_today(client):
    h = login(client, "student1@gramshiksha.in", "Learn@1234")
    path = client.get("/learn/path", headers=h).json()
    assert "continue" in path
    today = client.get("/learn/today", headers=h).json()
    assert today["date"] and isinstance(today["items"], list)
    assert today["study_minutes_today"] >= 0


def test_materials_upload_student_needs_review(client):
    s = login(client, "student2@gramshiksha.in", "Learn@1234")
    r = client.post("/materials", data={
        "title": "My notes", "type": "notes", "class_grade": 10, "board": "CBSE",
        "subject_name": "Science", "lang": "hi", "visibility": "public",
        "source_of_content": "Created by student"},
        files={"file": ("notes.txt", b"dummy", "text/plain")}, headers=s)
    assert r.status_code == 422  # txt not allowed
    r = client.post("/materials", data={
        "title": "My notes", "type": "notes", "class_grade": 10, "board": "CBSE",
        "subject_name": "Science", "lang": "hi", "visibility": "public",
        "source_of_content": "Created by student"},
        files={"file": ("notes.pdf", b"%PDF-1.4 fake", "application/pdf")}, headers=s)
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "pending"
    # teacher approves
    t = login(client, "teacher1@gramshiksha.in", "Teach@1234")
    pending = client.get("/materials/pending", headers=t).json()
    assert any(m["title"] == "My notes" for m in pending)
    mid = [m for m in pending if m["title"] == "My notes"][0]["id"]
    r = client.post(f"/materials/{mid}/review", data={"decision": "approved"}, headers=t)
    assert r.status_code == 200
    # now visible publicly
    visible = client.get("/materials", headers=s).json()
    assert any(m["id"] == mid for m in visible)


def test_doubts_flow(client):
    s = login(client, "student1@gramshiksha.in", "Learn@1234")
    r = client.post("/doubts", json={"subject_name": "Science", "chapter_title": "Living World",
                                     "text": "Why is the cell membrane selectively permeable?"}, headers=s)
    assert r.status_code == 201
    t = login(client, "teacher1@gramshiksha.in", "Teach@1234")
    doubts = client.get("/doubts", headers=t).json()
    assert doubts
    did = doubts[0]["id"]
    r = client.post(f"/doubts/{did}/reply", json={"body": "Because it controls what enters and leaves."}, headers=t)
    assert r.status_code == 201
    r = client.post(f"/doubts/{did}/resolve", headers=s)
    assert r.status_code == 200


def test_parent_dashboard(client):
    p = login(client, "parent1@gramshiksha.in", "Parent@1234")
    kids = client.get("/parent/children", headers=p).json()
    assert kids and kids[0]["name"] == "Arjun Kumar"
    assert "quiz_avg_pct" in kids[0] and "weak_subjects" in kids[0]


def test_role_guards(client):
    s = login(client, "student1@gramshiksha.in", "Learn@1234")
    assert client.get("/teacher/students", headers=s).status_code == 403
    assert client.get("/parent/children", headers=s).status_code == 403
    assert client.get("/admin/users", headers=s).status_code == 403
    t = login(client, "teacher1@gramshiksha.in", "Teach@1234")
    assert client.get("/teacher/students", headers=t).status_code == 200


def test_search(client):
    r = client.get("/search", params={"q": "cell"}).json()
    assert isinstance(r, dict)
