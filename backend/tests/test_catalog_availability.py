"""Catalog availability: the endpoint the UI trusts to never offer an empty
combination.

Contract under test: for one (board, class) it reports only mediums/subjects
that have actual rows (books, courses, or both); books count per language;
courses count with their *published* lessons; wrong grade/board never leaks;
an empty combo answers with empty lists, not an error. Literal paths on every
call because the route-coverage canary parses string literals.

Every fixture row uses a private board name: the test DB is shared across the
suite and `SEED_DEMO=auto` seeds real boards on SQLite, so a made-up board is
the only way to assert exact sets.
"""
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db import engine
from app.main import app
from app.models import Chapter, Course, Lesson, Subject, Textbook

BOARD = "Avail Test Board"
OTHER_BOARD = "Other Board"
PRIVATE_BOARDS = [BOARD, OTHER_BOARD]


@pytest.fixture(name="client")
def client_fixture():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _cleanup_private_boards():
    """The suite shares one DB and test_production asserts /textbooks/coverage
    lists exactly the three real boards — private-board rows must not outlive
    the test that created them.

    Children go first: with the default relationship cascade an ORM delete of
    a Course *nulls* chapter.course_id (NOT NULL) instead of removing the
    row, so lessons → chapters → courses → subjects, then books."""
    yield
    with Session(engine) as s:
        course_ids = [row.id for row in s.exec(
            select(Course).where(Course.board.in_(PRIVATE_BOARDS))).all()]
        chapter_ids = []
        if course_ids:
            chapter_ids = [row.id for row in s.exec(
                select(Chapter).where(Chapter.course_id.in_(course_ids))).all()]
        if chapter_ids:
            for les in s.exec(select(Lesson).where(Lesson.chapter_id.in_(chapter_ids))).all():
                s.delete(les)
            for ch in s.exec(select(Chapter).where(Chapter.id.in_(chapter_ids))).all():
                s.delete(ch)
        for c in s.exec(select(Course).where(Course.id.in_(course_ids))).all():
            s.delete(c)
        for subj in s.exec(select(Subject).where(Subject.board.in_(PRIVATE_BOARDS))).all():
            s.delete(subj)
        for t in s.exec(select(Textbook).where(Textbook.board.in_(PRIVATE_BOARDS))).all():
            s.delete(t)
        s.commit()


def _book(grade, subject, lang, title):
    return Textbook(board=BOARD, class_grade=grade, subject_name=subject,
                    lang=lang, title=title, source_url="https://books.ebalbharati.in/x")


def test_reports_only_mediums_that_actually_have_books(client):
    with Session(engine) as s:
        s.add(_book(7, "Mathematics", "mr", "Math 7 mr"))
        s.add(_book(7, "Mathematics", "en", "Math 7 en"))
        s.add(_book(7, "Science", "mr", "Science 7 mr"))
        # Leaks from neighbours — must never show up in grade 7's answer.
        s.add(_book(8, "History", "ur", "History 8 ur"))
        s.add(Textbook(board="Other Board", class_grade=7, subject_name="Physics",
                       lang="en", title="Physics 7", source_url="https://ncert.nic.in/x"))
        s.commit()

    r = client.get("/catalog/availability", params={"board": BOARD, "class_grade": 7})
    assert r.status_code == 200, r.text
    data = r.json()

    assert [m["lang"] for m in data["mediums"]] == ["en", "mr"]
    by_lang = {m["lang"]: m for m in data["mediums"]}
    assert by_lang["mr"]["books"] == 2 and by_lang["mr"]["subjects"] == 2
    assert by_lang["en"]["books"] == 1 and by_lang["en"]["subjects"] == 1
    # Label compared by codepoint, not by literal: a shell round-trip once
    # mojibake'd Devanagari in this file, so build the string from numbers.
    assert by_lang["mr"]["label"] == "".join(map(chr, [0x92E, 0x930, 0x93E, 0x920, 0x940]))

    subs = {s["name"]: s for s in data["subjects"]}
    assert set(subs) == {"Mathematics", "Science"}
    assert subs["Mathematics"]["books_by_lang"] == {"mr": 1, "en": 1}
    assert subs["Science"]["books_by_lang"] == {"mr": 1}

    # Literal twin behind the production /api rewrite (canary needs both).
    assert client.get(
        "/api/catalog/availability", params={"board": BOARD, "class_grade": 7}
    ).status_code == 200


def test_courses_count_with_published_lessons_only(client):
    with Session(engine) as s:
        subj = Subject(name_en="AvailMath", name_hi="Math hi", name_mr="Math mr",
                       class_grade=6, board=BOARD)
        s.add(subj)
        s.commit()
        s.refresh(subj)
        course = Course(slug="avail-c6-math", subject_id=subj.id, board=BOARD,
                        class_grade=6, title_en="Math 6", title_hi="Math 6 hi",
                        title_mr="Math 6 mr")
        s.add(course)
        s.commit()
        s.refresh(course)
        ch = Chapter(course_id=course.id, title_en="Ch1", title_hi="Ch1 hi",
                     title_mr="Ch1 mr")
        s.add(ch)
        s.commit()
        s.refresh(ch)
        s.add(Lesson(chapter_id=ch.id, title_en="L1", title_hi="L1 hi",
                     title_mr="L1 mr"))
        s.add(Lesson(chapter_id=ch.id, title_en="Draft", title_hi="Draft hi",
                     title_mr="Draft mr", published=False))
        s.commit()
        subj_id, course_id = subj.id, course.id

    data = client.get(
        "/catalog/availability", params={"board": BOARD, "class_grade": 6}
    ).json()
    math = next(x for x in data["subjects"] if x["name"] == "AvailMath")
    assert math["courses"] == 1
    assert math["lessons"] == 1  # the unpublished draft is not counted
    assert math["name_hi"] == "Math hi"  # translations ride along when known
    # Deep-link handles the UI routes with: subject filter + first lesson.
    assert math["subject_id"] == subj_id
    assert math["course_ids"] == [course_id]


def test_empty_combo_is_empty_lists_not_an_error(client):
    r = client.get("/catalog/availability", params={"board": BOARD, "class_grade": 9})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["mediums"] == []
    assert data["subjects"] == []


def test_availability_concurrent_reads_are_isolated(client):
    def read_availability(_):
        return client.get(
            "/catalog/availability", params={"board": BOARD, "class_grade": 9}
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        responses = list(executor.map(read_availability, range(32)))
    assert all(response.status_code == 200 for response in responses), [
        response.text for response in responses if response.status_code != 200
    ]


def test_grade_bounds_are_validated(client):
    assert client.get(
        "/catalog/availability", params={"board": BOARD, "class_grade": 13}
    ).status_code == 422
    assert client.get(
        "/catalog/availability", params={"board": BOARD, "class_grade": 0}
    ).status_code == 422
