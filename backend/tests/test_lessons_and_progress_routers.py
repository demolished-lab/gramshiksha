"""Coverage for the two repaired routers: /lessons (6) and /progress/* (4).

Both routers existed on disk, were never mounted, and referenced schema that
never existed (`Lesson.subject`/`level`, `Question.correct_index`,
`QuizAttempt.lesson_id`, a `Batch` model with no table). This suite pins the
repaired contract: who may author, how answers are graded, that drafts stay
invisible to students, and that history/rollup rows really appear after a
lesson completion and a quiz attempt.

The canary in test_route_coverage_canary.py fails if any of these endpoints is
ever mounted without a test here.
"""
import uuid

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


def signup(client, email, role="student", grade=8, board="Maharashtra SSC"):
    r = client.post("/auth/register", json={
        "email": email, "name": "Probe User", "password": "Original@123",
        "role": role, "class_grade": grade, "board": board})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, r.json()["id"]


def grade8_context(client):
    """(chapter_id, chapter_ids_of_course, lesson_id, course_id) for Class 8."""
    courses = client.get("/courses", params={"class_grade": 8, "board": "Maharashtra SSC"}).json()
    course = client.get(f"/courses/{courses['items'][0]['id']}").json()
    chapter_ids = [ch["id"] for ch in course["chapters"]]
    lesson_id = course["chapters"][0]["lessons"][0]["id"]
    return course["chapters"][0]["id"], chapter_ids, lesson_id, course["id"]


def make_lesson(client, teacher, chapter_id, title_en=None, **overrides):
    # Unique by default: tests share one database for the whole run, and the
    # router rejects a duplicate title inside a chapter (by design).
    if title_en is None:
        title_en = f"Probe lesson {uuid.uuid4().hex[:8]}"
    payload = {
        "chapter_id": chapter_id, "type": "text",
        "title_en": title_en, "title_hi": "नया पाठ", "title_mr": "नवीन धडा",
        "body_en": "A body written by a teacher through the API.",
        "body_hi": "शिक्षक ने एपीआई से लिखा।", "body_mr": "शिक्षकानीने एपीआई ने लिहिले।",
        "duration_min": 9,
    }
    payload.update(overrides)
    r = client.post("/lessons", json=payload, headers=teacher)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def add_question(client, teacher, lesson_id, **overrides):
    payload = {
        "type": "mcq", "prompt_en": "Which part holds the cell together?",
        "prompt_hi": "कोशिका को कौन-सा भाग जोड़े रखता है?", "prompt_mr": "कोशिकेला कोणता भाग जोडून ठेवतो?",
        "options_en": ["Cell wall", "Nucleus"], "options_hi": ["कोशिका भित्ति", "केंद्रक"],
        "options_mr": ["पेशीभित्ती", "केंद्रक"],
        "correct": "0", "explanation_en": "The cell wall gives shape and support.",
        "explanation_hi": "कोशिका भित्ति आकार और सहारा देती है।",
        "explanation_mr": "पेशीभित्ती आकार व आधार देते.",
        "difficulty": "easy", "topic": "cells", "subject_name": "Science",
    }
    payload.update(overrides)
    r = client.post(f"/lessons/{lesson_id}/questions", json=payload, headers=teacher)
    return r


# ---------- GET /lessons ----------

def test_list_lessons_filters_and_pagination(client):
    h, _ = signup(client, "listreader@x.in")
    chapter_id, chapter_ids, _, course_id = grade8_context(client)

    everything = client.get("/lessons", params={"limit": 100}, headers=h)
    assert everything.status_code == 200, everything.text
    rows = everything.json()
    assert len(rows) >= 10, "seed should publish well over ten lessons"
    assert all(r["published"] and r["chapter_id"] for r in rows)

    # limit/offset slice the same ordered list
    page = client.get("/lessons", params={"limit": 3, "offset": 2}, headers=h).json()
    assert [r["id"] for r in page] == [r["id"] for r in rows[2:5]]

    # course scoping joins through the chapter
    scoped = client.get("/lessons", params={"course_id": course_id, "limit": 100},
                        headers=h).json()
    assert scoped and all(r["chapter_id"] in chapter_ids for r in scoped)

    videos = client.get("/lessons", params={"type": "video", "limit": 100}, headers=h).json()
    assert videos and all(r["type"] == "video" for r in videos)

    assert client.get("/lessons", params={"type": "hologram"}, headers=h).status_code == 422
    assert client.get("/lessons", params={"limit": 500}, headers=h).status_code == 422
    assert client.get("/lessons").status_code == 401


# ---------- GET /lessons/{id} ----------

def test_lesson_detail_hides_drafts_from_students(client):
    teacher = login(client, "teacher1@gramshiksha.in", "Teach@1234")
    student, _ = signup(client, "draftreader@x.in")
    chapter_id, _, published_id, _ = grade8_context(client)

    # A published lesson reads back exactly as authored.
    body = client.get(f"/lessons/{published_id}", headers=student)
    assert body.status_code == 200, body.text
    assert body.json()["id"] == published_id and body.json()["published"] is True

    # A draft exists for its author, not for learners — and never lists.
    draft_id = make_lesson(client, teacher, chapter_id,
                           title_en="Unpublished draft", published=False)
    assert client.get(f"/lessons/{draft_id}", headers=teacher).status_code == 200
    assert client.get(f"/lessons/{draft_id}", headers=student).status_code == 404
    listed = client.get("/lessons", params={"limit": 100, "chapter_id": chapter_id},
                        headers=student).json()
    assert draft_id not in [r["id"] for r in listed]

    assert client.get("/lessons/999999", headers=student).status_code == 404
    assert client.get(f"/lessons/{published_id}").status_code == 401


def test_lesson_questions_never_leak_answers(client):
    teacher = login(client, "teacher1@gramshiksha.in", "Teach@1234")
    student, _ = signup(client, "qreader@x.in")
    chapter_id, _, _, _ = grade8_context(client)
    lesson_id = make_lesson(client, teacher, chapter_id)

    created = add_question(client, teacher, lesson_id)
    assert created.status_code == 201, created.text

    r = client.get(f"/lessons/{lesson_id}/questions", headers=student)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) == 1
    q = rows[0]
    assert q["type"] == "mcq" and q["topic"] == "cells"
    assert q["options_en"] == ["Cell wall", "Nucleus"]   # parsed, not a raw JSON string
    assert q["correct"] is None                          # answers hidden until grading
    assert q["explanation_en"] is None and q["explanation_mr"] is None

    assert client.get("/lessons/999999/questions", headers=student).status_code == 404
    assert client.get(f"/lessons/{lesson_id}/questions").status_code == 401


# ---------- POST /lessons ----------

def test_teacher_creates_a_lesson(client):
    teacher = login(client, "teacher1@gramshiksha.in", "Teach@1234")
    student, _ = signup(client, "author@x.in")
    chapter_id, _, _, _ = grade8_context(client)

    r = client.post("/lessons", json={
        "chapter_id": chapter_id, "type": "text",
        "title_en": "Photosynthesis in short", "title_hi": "प्रकाश संश्लेषण",
        "title_mr": "प्रकाशसंश्लेषण", "body_en": "Plants make food from light.",
        "body_hi": "पौधे प्रकाश से भोजन बनाते हैं।", "body_mr": "रोपे प्रकाशाहून अन्न तयार करतात.",
        "duration_min": 12}, headers=teacher)
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["id"] and created["title_en"] == "Photosynthesis in short"
    assert created["order"] >= 1 and created["published"] is True

    # readable through the plain detail route and listed in its chapter
    assert client.get(f"/lessons/{created['id']}", headers=teacher).json()["body_hi"]

    # duplicate title inside one chapter is refused, not silently repeated
    dup = client.post("/lessons", json={
        "chapter_id": chapter_id, "title_en": "Photosynthesis in short",
        "title_hi": "x", "title_mr": "y"}, headers=teacher)
    assert dup.status_code == 409

    # unknown chapter / bad type / non-teacher are all rejected
    assert client.post("/lessons", json={"chapter_id": 999999, "title_en": "a",
                                         "title_hi": "b", "title_mr": "c"},
                       headers=teacher).status_code == 404
    assert client.post("/lessons", json={
        "chapter_id": chapter_id, "type": "telepathy", "title_en": "a",
        "title_hi": "b", "title_mr": "c"}, headers=teacher).status_code == 422
    assert client.post("/lessons", json={
        "chapter_id": chapter_id, "title_en": "a", "title_hi": "b", "title_mr": "c"},
        headers=student).status_code == 403
    assert client.post("/lessons", json={
        "chapter_id": chapter_id, "title_en": "a"}).status_code == 401
    # missing translation is a schema error, not a half-written row
    assert client.post("/lessons", json={"chapter_id": chapter_id, "title_en": "only english"},
                       headers=teacher).status_code == 422


def test_question_validation_matches_the_grader(client):
    teacher = login(client, "teacher1@gramshiksha.in", "Teach@1234")
    chapter_id, _, _, _ = grade8_context(client)
    lesson_id = make_lesson(client, teacher, chapter_id)

    def attempt(payload):
        return add_question(client, teacher, lesson_id, **payload)

    # correct index must address an existing option
    assert attempt({"correct": "7"}).status_code == 422
    # option lists must line up across the three languages
    assert attempt({"options_hi": ["only-one"]}).status_code == 422
    # true/false carries no options of its own
    assert attempt({"type": "truefalse", "options_en": ["a", "b"],
                    "options_hi": ["a", "b"], "options_mr": ["a", "b"]}).status_code == 422
    assert attempt({"type": "truefalse", "correct": "2"}).status_code == 422
    # fill-in questions take free text and no options
    assert attempt({"type": "fill", "correct": "  "}).status_code == 422
    assert attempt({"type": "fill", "correct": "cell",
                    "options_en": ["a", "b"]}).status_code == 422
    # multi needs a JSON index list
    assert attempt({"type": "multi", "correct": "0"}).status_code == 422
    assert attempt({"type": "multi", "correct": "[0,9]"}).status_code == 422
    assert attempt({"type": "riddle", "correct": "0"}).status_code == 422
    assert attempt({"difficulty": "impossible"}).status_code == 422

    # and the legal shapes are accepted (no options on these two types)
    assert attempt({"type": "truefalse", "correct": "1",
                    "options_en": [], "options_hi": [], "options_mr": []}).status_code == 201
    assert attempt({"type": "fill", "correct": "cell",
                    "options_en": [], "options_hi": [], "options_mr": []}).status_code == 201
    assert attempt({"type": "multi", "correct": "[0,1]"}).status_code == 201

    # a lesson that does not exist cannot take questions
    assert add_question(client, teacher, 999999).status_code == 404
    assert add_question(client, {"Authorization": "Bearer nope"}, lesson_id).status_code == 401


# ---------- POST /lessons/{id}/attempt ----------

def test_lesson_attempt_grades_and_keeps_the_best_score(client):
    teacher = login(client, "teacher1@gramshiksha.in", "Teach@1234")
    student, _ = signup(client, "attempter@x.in")
    chapter_id, _, _, _ = grade8_context(client)
    lesson_id = make_lesson(client, teacher, chapter_id)

    mcq = add_question(client, teacher, lesson_id).json()["id"]
    fill = add_question(client, teacher, lesson_id, type="fill", correct="cell",
                        options_en=[], options_hi=[], options_mr=[],
                        prompt_en="The unit of life is the ___.",
                        prompt_hi="जीवन की इकाई ___ है।",
                        prompt_mr="जीवनाची एकक ___ आहे.").json()["id"]

    perfect = [{"question_id": mcq, "answer": 0}, {"question_id": fill, "answer": "Cell"}]
    r = client.post(f"/lessons/{lesson_id}/attempt",
                    json={"answers": perfect, "minutes": 6}, headers=student)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 2 and body["correct"] == 2 and body["score"] == 100.0
    step = body["per_question"][0]
    assert set(step) == {"question_id", "chosen", "correct_answer", "ok", "explanation"}
    assert step["ok"] is True and step["correct_answer"] == 0
    assert step["explanation"]["en"] and step["explanation"]["mr"]

    # The lesson shows as done on the history endpoint.
    rows = client.get("/progress/me", headers=student).json()
    assert [r["lesson_id"] for r in rows] == [lesson_id]
    assert rows[0]["completed"] is True and rows[0]["score"] == 100.0

    # A later, worse attempt must not erase the best score.
    worse = [{"question_id": mcq, "answer": 1}, {"question_id": fill, "answer": "wrong"}]
    r = client.post(f"/lessons/{lesson_id}/attempt",
                    json={"answers": worse, "minutes": 1}, headers=student)
    assert r.status_code == 200
    assert r.json()["score"] == 0.0
    rows = client.get("/progress/me", headers=student).json()
    assert rows[0]["score"] == 100.0, "best score must survive a worse retry"

    # Answers to questions that do not belong to this lesson are refused.
    other = make_lesson(client, teacher, chapter_id, title_en="Some other lesson")
    foreign = add_question(client, teacher, other).json()["id"]
    assert client.post(f"/lessons/{lesson_id}/attempt",
                       json={"answers": [{"question_id": mcq, "answer": 0},
                                         {"question_id": foreign, "answer": 0}]},
                       headers=student).status_code == 422
    # Wrong count, and the same question twice, are refused too.
    assert client.post(f"/lessons/{lesson_id}/attempt",
                       json={"answers": [{"question_id": mcq, "answer": 0}]},
                       headers=student).status_code == 422
    assert client.post(f"/lessons/{lesson_id}/attempt",
                       json={"answers": [{"question_id": mcq, "answer": 0},
                                         {"question_id": mcq, "answer": 1}]},
                       headers=student).status_code == 422

    # Attempts are for students, on lessons that exist.
    assert client.post(f"/lessons/{lesson_id}/attempt", json={"answers": perfect},
                       headers=teacher).status_code == 403
    assert client.post("/lessons/999999/attempt", json={"answers": perfect},
                       headers=student).status_code == 404
    assert client.post(f"/lessons/{lesson_id}/attempt",
                       json={"answers": perfect}).status_code == 401

    empty = make_lesson(client, teacher, chapter_id, title_en="Lesson with no questions")
    assert client.post(f"/lessons/{empty}/attempt", json={"answers": perfect},
                       headers=student).status_code == 422


# ---------- /progress history ----------

def test_progress_history_and_attempt_log(client):
    h, _ = signup(client, "history@x.in")
    chapter_id, _, lesson_id, _ = grade8_context(client)

    # Empty before any studying happens.
    assert client.get("/progress/me", headers=h).json() == []
    assert client.get("/progress/me/attempts", headers=h).json() == []

    # Completing a lesson through the live endpoint lands a row here.
    done = client.post(f"/learn/lessons/{lesson_id}/complete",
                       params={"minutes": 9}, headers=h)
    assert done.status_code == 200
    rows = client.get("/progress/me", headers=h).json()
    assert len(rows) == 1
    assert rows[0]["lesson_id"] == lesson_id and rows[0]["completed"] is True
    assert rows[0]["updated_at"]

    # Taking the chapter's quiz lands an attempt, with its lesson resolved.
    quiz = client.get(f"/learn/quizzes-by-chapter/{chapter_id}", headers=h).json()
    assert quiz["questions"]
    submit = client.post(f"/learn/quizzes/{quiz['id']}/submit", json={
        "answers": [{"question_id": q["id"], "answer": 0} for q in quiz["questions"]],
        "time_taken_s": 120}, headers=h)
    assert submit.status_code == 200

    attempts = client.get("/progress/me/attempts", headers=h).json()
    assert len(attempts) == 1
    a = attempts[0]
    assert a["quiz_id"] == quiz["id"] and a["chapter_id"] == chapter_id
    assert 0.0 <= a["percentage"] <= 100.0
    assert a["time_taken_s"] == 120 and a["created_at"]

    assert client.get("/progress/me").status_code == 401
    assert client.get("/progress/me/attempts").status_code == 401


def test_teacher_attempt_overview(client):
    teacher = login(client, "teacher1@gramshiksha.in", "Teach@1234")
    student = login(client, "student1@gramshiksha.in", "Learn@1234")

    # Take a quiz here so the averages have something to compute, regardless
    # of which tests have run before this one.
    chapter_id, _, _, _ = grade8_context(client)
    quiz = client.get(f"/learn/quizzes-by-chapter/{chapter_id}", headers=student).json()
    assert quiz["questions"]
    assert client.post(f"/learn/quizzes/{quiz['id']}/submit", json={
        "answers": [{"question_id": q["id"], "answer": 0} for q in quiz["questions"]],
        "time_taken_s": 60}, headers=student).status_code == 200

    r = client.get("/progress/teacher/overview", headers=teacher)
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"students", "total_attempts", "overall_avg_score"}
    assert body["students"], "seeded students must be listed"
    row = body["students"][0]
    assert set(row) == {"id", "name", "email", "attempts", "avg_score"}
    assert row["attempts"] >= 0
    if row["attempts"]:
        assert 0.0 <= row["avg_score"] <= 100.0
    assert body["total_attempts"] >= 1           # the suite has taken quizzes by now
    assert 0.0 <= body["overall_avg_score"] <= 100.0

    assert client.get("/progress/teacher/overview", headers=student).status_code == 403
    assert client.get("/progress/teacher/overview").status_code == 401
    assert client.get("/api/progress/teacher/overview", headers=teacher).status_code == 200


def test_create_batch(client):
    teacher = login(client, "teacher1@gramshiksha.in", "Teach@1234")
    student = login(client, "student1@gramshiksha.in", "Learn@1234")
    teacher_id = client.get("/auth/me", headers=teacher).json()["id"]

    r = client.post("/progress/batches",
                    json={"name": "  Class 8-A  ", "description": "Morning section"},
                    headers=teacher)
    assert r.status_code == 201, r.text
    batch = r.json()
    assert batch["name"] == "Class 8-A"           # trimmed on the way in
    assert batch["description"] == "Morning section"
    assert batch["teacher_id"] == teacher_id and batch["id"] and batch["created_at"]

    # Blank, whitespace-only and missing names never reach the table.
    assert client.post("/progress/batches", json={"name": ""}, headers=teacher).status_code == 422
    assert client.post("/progress/batches", json={"name": "   "}, headers=teacher).status_code == 422
    assert client.post("/progress/batches", json={"description": "no name"},
                       headers=teacher).status_code == 422

    # Authoring a batch is a teacher action.
    assert client.post("/progress/batches", json={"name": "X"},
                       headers=student).status_code == 403
    assert client.post("/progress/batches", json={"name": "X"}).status_code == 401
