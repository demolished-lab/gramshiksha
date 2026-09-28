"""Lesson authoring and lesson-level practice on the /lessons prefix.

History: this router predates learn.py, was never mounted, and referenced
columns that do not exist (`Lesson.subject` / `Lesson.level`,
`Question.correct_index`), so importing it would have failed at request time.
It is now wired to the real schema and mounted bare + under /api like every
other router.

Division of labour with learn.py:

* `learn.py` is the *player* — it requires a session, returns the localized
  body, records completion and hides answers.
* this router is the *authoring* surface — teachers list/create lessons and
  their questions here, and students grade a lesson's questions in one shot.

Grading deliberately reuses `learn._grade` so a lesson attempt and a quiz
answer can never disagree about what counts as correct.
"""
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from ..db import get_session
from ..gamification import log_study_time
from ..models import Chapter, Lesson, Progress, Question, User, utcnow
from ..schemas import AttemptIn, AttemptOut, LessonCreate, LessonRead, QuestionIn, QuestionOut
from ..security import get_current_user, has_role, require_student, require_teacher
from .learn import _grade, _record_topic

router = APIRouter(prefix="/lessons", tags=["lessons"])

LESSON_TYPES = ("text", "video", "audio", "mixed")
QUESTION_TYPES = ("mcq", "truefalse", "multi", "fill")
DIFFICULTIES = ("easy", "medium", "hard")
MODERATOR_ROLES = ("teacher", "school_admin", "platform_admin")


def _options(raw: str) -> list[str]:
    return json.loads(raw or "[]")


def _question_out(q: Question, reveal: bool = False) -> dict:
    return {
        "id": q.id, "type": q.type,
        "prompt_en": q.prompt_en, "prompt_hi": q.prompt_hi, "prompt_mr": q.prompt_mr,
        "options_en": _options(q.options_en), "options_hi": _options(q.options_hi),
        "options_mr": _options(q.options_mr),
        "difficulty": q.difficulty, "topic": q.topic, "subject_name": q.subject_name,
        "correct": q.correct if reveal else None,
        "explanation_en": q.explanation_en if reveal else None,
        "explanation_hi": q.explanation_hi if reveal else None,
        "explanation_mr": q.explanation_mr if reveal else None,
    }


def _validate_question(p: QuestionIn) -> None:
    """Reject a question the grader could not possibly judge later."""
    if p.type not in QUESTION_TYPES:
        raise HTTPException(422, f"type must be one of {QUESTION_TYPES}")
    if p.difficulty not in DIFFICULTIES:
        raise HTTPException(422, f"difficulty must be one of {DIFFICULTIES}")

    if p.type in ("fill", "truefalse"):
        if p.options_en or p.options_hi or p.options_mr:
            raise HTTPException(422, f"{p.type} questions carry no options")
        if p.type == "fill":
            if not p.correct.strip():
                raise HTTPException(422, "fill questions need a non-empty correct answer")
        elif p.correct not in ("0", "1"):
            raise HTTPException(422, 'truefalse correct must be "0" or "1"')
        return

    if not p.options_en:
        raise HTTPException(422, "mcq/multi questions need options")
    if not (len(p.options_en) == len(p.options_hi) == len(p.options_mr)):
        raise HTTPException(422, "options must be the same length in en, hi and mr")
    count = len(p.options_en)

    if p.type == "mcq":
        try:
            index = int(p.correct)
        except ValueError:
            raise HTTPException(422, "mcq correct must be an option index")
        if not 0 <= index < count:
            raise HTTPException(422, "correct index out of range")
        return

    # multi: a JSON list of indices, e.g. "[0,2]"
    try:
        picked = json.loads(p.correct)
    except ValueError:
        raise HTTPException(422, 'multi correct must be a JSON list, e.g. "[0,2]"')
    if not isinstance(picked, list) or not picked:
        raise HTTPException(422, "multi correct must name at least one option")
    if any(not isinstance(i, int) or not 0 <= i < count for i in picked):
        raise HTTPException(422, "correct index out of range")


# ---------- read side ----------

@router.get("", response_model=list[LessonRead])
def list_lessons(chapter_id: Optional[int] = None,
                 course_id: Optional[int] = None,
                 type: Optional[str] = None,
                 limit: int = Query(20, ge=1, le=100),
                 offset: int = Query(0, ge=0),
                 session: Session = Depends(get_session),
                 user: User = Depends(get_current_user)) -> list[Lesson]:
    """Published lessons, optionally narrowed to one chapter or course."""
    if type and type not in LESSON_TYPES:
        raise HTTPException(422, f"type must be one of {LESSON_TYPES}")
    q = (select(Lesson)
         .join(Chapter, Chapter.id == Lesson.chapter_id)
         .where(Lesson.published == True))  # noqa: E712
    if chapter_id:
        q = q.where(Lesson.chapter_id == chapter_id)
    if course_id:
        q = q.where(Chapter.course_id == course_id)
    if type:
        q = q.where(Lesson.type == type)
    q = q.order_by(Lesson.chapter_id, Lesson.order).offset(offset).limit(limit)
    return list(session.exec(q).all())


@router.get("/{lesson_id}", response_model=LessonRead)
def get_lesson(lesson_id: int, session: Session = Depends(get_session),
               user: User = Depends(get_current_user)) -> Lesson:
    lesson = session.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(404, "Lesson not found")
    # Drafts stay invisible to students, but a teacher can preview their own.
    if not lesson.published and not has_role(user, *MODERATOR_ROLES):
        raise HTTPException(404, "Lesson not found")
    return lesson


@router.get("/{lesson_id}/questions", response_model=list[QuestionOut])
def get_questions(lesson_id: int, session: Session = Depends(get_session),
                  user: User = Depends(get_current_user)) -> list[dict]:
    if not session.get(Lesson, lesson_id):
        raise HTTPException(404, "Lesson not found")
    rows = session.exec(select(Question)
                        .where(Question.lesson_id == lesson_id)
                        .order_by(Question.id)).all()
    # Answers are never served by a plain read — grading endpoints reveal them.
    return [_question_out(q) for q in rows]


# ---------- write side ----------

@router.post("", response_model=LessonRead, status_code=201)
def create_lesson(payload: LessonCreate, session: Session = Depends(get_session),
                  teacher: User = Depends(require_teacher)) -> Lesson:
    if payload.type not in LESSON_TYPES:
        raise HTTPException(422, f"type must be one of {LESSON_TYPES}")
    if not session.get(Chapter, payload.chapter_id):
        raise HTTPException(404, "Chapter not found")
    dup = session.exec(select(Lesson).where(
        Lesson.chapter_id == payload.chapter_id,
        Lesson.title_en == payload.title_en)).first()
    if dup:
        raise HTTPException(409, "A lesson with this title already exists in the chapter")

    orders = session.exec(select(Lesson.order).where(
        Lesson.chapter_id == payload.chapter_id)).all()
    lesson = Lesson(**payload.model_dump(), order=(max(orders) if orders else 0) + 1)
    session.add(lesson)
    session.commit()
    session.refresh(lesson)
    return lesson


@router.post("/{lesson_id}/questions", status_code=201)
def add_question(lesson_id: int, payload: QuestionIn,
                 session: Session = Depends(get_session),
                 teacher: User = Depends(require_teacher)) -> dict:
    if not session.get(Lesson, lesson_id):
        raise HTTPException(404, "Lesson not found")
    _validate_question(payload)
    q = Question(
        lesson_id=lesson_id, type=payload.type,
        prompt_en=payload.prompt_en, prompt_hi=payload.prompt_hi, prompt_mr=payload.prompt_mr,
        options_en=json.dumps(payload.options_en, ensure_ascii=False),
        options_hi=json.dumps(payload.options_hi, ensure_ascii=False),
        options_mr=json.dumps(payload.options_mr, ensure_ascii=False),
        correct=payload.correct,
        explanation_en=payload.explanation_en, explanation_hi=payload.explanation_hi,
        explanation_mr=payload.explanation_mr,
        difficulty=payload.difficulty, topic=payload.topic, subject_name=payload.subject_name,
    )
    session.add(q)
    session.commit()
    session.refresh(q)
    return {"id": q.id}


@router.post("/{lesson_id}/attempt", response_model=AttemptOut)
def submit_attempt(lesson_id: int, payload: AttemptIn,
                   session: Session = Depends(get_session),
                   user: User = Depends(require_student)) -> AttemptOut:
    """Grade one attempt over a lesson's own questions.

    The answers are matched by question id (not by position), every question on
    the lesson must be answered exactly once, and the best score so far is kept
    on the Progress row — same semantics as the quiz engine.
    """
    lesson = session.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(404, "Lesson not found")
    questions = session.exec(select(Question)
                             .where(Question.lesson_id == lesson_id)
                             .order_by(Question.id)).all()
    if not questions:
        raise HTTPException(422, "Lesson has no questions")
    if len(payload.answers) != len(questions):
        raise HTTPException(422, "answers length mismatch")

    by_id = {q.id: q for q in questions}
    given: dict[int, object] = {}
    for answer in payload.answers:
        if answer.question_id not in by_id:
            raise HTTPException(422, "answer refers to a question on another lesson")
        if answer.question_id in given:
            raise HTTPException(422, "duplicate answer for a question")
        given[answer.question_id] = answer.answer

    score = correct = 0
    per_question = []
    for q in questions:
        chosen = given[q.id]
        ok, expected = _grade(q, chosen)
        correct += int(ok)
        per_question.append({
            "question_id": q.id, "chosen": chosen, "correct_answer": expected, "ok": ok,
            "explanation": {"en": q.explanation_en, "hi": q.explanation_hi,
                            "mr": q.explanation_mr},
        })
        _record_topic(session, user, q, ok)
    score = round(100.0 * correct / len(questions), 1)

    prog = session.exec(select(Progress).where(
        Progress.user_id == user.id, Progress.lesson_id == lesson_id)).first()
    if not prog:
        prog = Progress(user_id=user.id, lesson_id=lesson_id)
    prog.completed = True
    prog.score = max(prog.score or 0.0, score)
    prog.updated_at = utcnow()
    session.add(prog)
    if payload.minutes:
        log_study_time(session, user, payload.minutes)
    session.add(user)
    session.commit()

    return AttemptOut(score=score, total=len(questions), correct=correct,
                      per_question=per_question)
