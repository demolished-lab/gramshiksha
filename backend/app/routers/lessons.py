import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from ..db import get_session
from ..models import Lesson, Question, QuizAttempt, User, utcnow
from ..schemas import AttemptIn, AttemptOut, LessonCreate, LessonRead, QuestionIn, QuestionOut
from ..security import get_current_user, require_teacher

router = APIRouter(prefix="/lessons", tags=["lessons"])


@router.get("", response_model=list[LessonRead])
def list_lessons(
    subject: str | None = Query(None),
    level: int | None = Query(None),
    session: Session = Depends(get_session),
) -> list[Lesson]:
    q = select(Lesson).where(Lesson.published == True)  # noqa: E712
    if subject:
        q = q.where(Lesson.subject == subject)
    if level:
        q = q.where(Lesson.level == level)
    return list(session.exec(q.order_by(Lesson.level, Lesson.id)).all())


@router.get("/{lesson_id}", response_model=LessonRead)
def get_lesson(lesson_id: int, session: Session = Depends(get_session)) -> Lesson:
    lesson = session.get(Lesson, lesson_id)
    if not lesson or not lesson.published:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return lesson


@router.get("/{lesson_id}/questions", response_model=list[QuestionOut])
def get_questions(lesson_id: int, session: Session = Depends(get_session)) -> list[QuestionOut]:
    lesson = session.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    rows = session.exec(select(Question).where(Question.lesson_id == lesson_id)).all()
    # Hide answers from students; expose count for quiz UI
    out = []
    for r in rows:
        out.append(
            QuestionOut(
                id=r.id,
                prompt_en=r.prompt_en,
                prompt_hi=r.prompt_hi,
                options_en=r.options_en,
                options_hi=r.options_hi,
                correct_index=None,
                explanation_en=None,
                explanation_hi=None,
            )
        )
    return out


@router.post("", response_model=LessonRead, status_code=201)
def create_lesson(
    payload: LessonCreate,
    session: Session = Depends(get_session),
    teacher: User = Depends(require_teacher),
) -> Lesson:
    dup = session.exec(select(Lesson).where(Lesson.slug == payload.slug)).first()
    if dup:
        raise HTTPException(status_code=409, detail="Slug already exists")
    lesson = Lesson(**payload.model_dump(), author_id=teacher.id)
    session.add(lesson)
    session.commit()
    session.refresh(lesson)
    return lesson


@router.post("/{lesson_id}/questions", status_code=201)
def add_question(
    lesson_id: int,
    payload: QuestionIn,
    session: Session = Depends(get_session),
    teacher: User = Depends(require_teacher),
) -> dict:
    if not session.get(Lesson, lesson_id):
        raise HTTPException(status_code=404, detail="Lesson not found")
    if payload.correct_index >= len(payload.options_en):
        raise HTTPException(status_code=422, detail="correct_index out of range")
    q = Question(
        lesson_id=lesson_id,
        prompt_en=payload.prompt_en,
        prompt_hi=payload.prompt_hi,
        options_en=json.dumps(payload.options_en, ensure_ascii=False),
        options_hi=json.dumps(payload.options_hi, ensure_ascii=False),
        correct_index=payload.correct_index,
        explanation_en=payload.explanation_en,
        explanation_hi=payload.explanation_hi,
    )
    session.add(q)
    session.commit()
    session.refresh(q)
    return {"id": q.id}


@router.post("/{lesson_id}/attempt", response_model=AttemptOut)
def submit_attempt(
    lesson_id: int,
    payload: AttemptIn,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> AttemptOut:
    if not session.get(Lesson, lesson_id):
        raise HTTPException(status_code=404, detail="Lesson not found")
    questions = session.exec(select(Question).where(Question.lesson_id == lesson_id)).all()
    if not questions:
        raise HTTPException(status_code=422, detail="Lesson has no questions")
    if len(payload.answers) != len(questions):
        raise HTTPException(status_code=422, detail="answers length mismatch")

    per_question = []
    correct = 0
    for q, ans in zip(questions, payload.answers):
        ok = int(ans) == q.correct_index
        correct += int(ok)
        per_question.append(
            {
                "question_id": q.id,
                "chosen": ans,
                "correct_index": q.correct_index,
                "ok": ok,
                "explanation_en": q.explanation_en,
                "explanation_hi": q.explanation_hi,
            }
        )
    score = round(100.0 * correct / len(questions), 2)

    attempt = QuizAttempt(user_id=user.id, lesson_id=lesson_id, answers=json.dumps(payload.answers), score=score)
    session.add(attempt)
    # Upsert progress (SQLite/Postgres portable)
    from ..models import Progress

    prog = session.exec(
        select(Progress).where(Progress.user_id == user.id, Progress.lesson_id == lesson_id)
    ).first()
    if prog:
        prog.score = max(prog.score or 0, score)
        prog.completed = True
        prog.updated_at = utcnow()
    else:
        session.add(Progress(user_id=user.id, lesson_id=lesson_id, completed=True, score=score))
    session.commit()
    return AttemptOut(score=score, total=len(questions), correct=correct, per_question=per_question)
