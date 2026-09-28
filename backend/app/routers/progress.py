"""Per-student history and teacher analytics on the /progress prefix.

History: like lessons.py this router was written against an earlier schema,
never mounted, and would not import — `QuizAttempt` has never had a `lesson_id`
column (attempts belong to a quiz) and the `Batch` model it created rows for
did not exist. It is now mounted bare + under /api.

Note `dashboards.py` owns the *rollups* (`/progress/summary`, `/progress/weekly`,
`/teacher/overview`); this router is the raw per-row history behind them:
every progress row and every attempt for the signed-in student, plus the
teacher's per-student attempt table.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..db import get_session
from ..models import Batch, Progress, Quiz, QuizAttempt, User
from ..schemas import BatchIn, ProgressOut
from ..security import get_current_user, require_teacher

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("/me", response_model=list[ProgressOut])
def my_progress(session: Session = Depends(get_session),
                user: User = Depends(get_current_user)) -> list[Progress]:
    """Every lesson row this student has touched, newest first."""
    rows = session.exec(select(Progress)
                        .where(Progress.user_id == user.id)
                        .order_by(Progress.updated_at.desc())).all()
    return list(rows)


@router.get("/me/attempts")
def my_attempts(session: Session = Depends(get_session),
                user: User = Depends(get_current_user)) -> list[dict]:
    """Quiz attempt history, with the quiz's lesson/chapter resolved.

    Attempts store `quiz_id` — the older code read `QuizAttempt.lesson_id`,
    which is why this endpoint was unreachable: it cannot work without joining
    through the quiz.
    """
    rows = session.exec(select(QuizAttempt)
                        .where(QuizAttempt.user_id == user.id)
                        .order_by(QuizAttempt.created_at.desc())).all()
    out = []
    for r in rows:
        quiz: Optional[Quiz] = session.get(Quiz, r.quiz_id)
        out.append({
            "id": r.id, "quiz_id": r.quiz_id,
            "lesson_id": quiz.lesson_id if quiz else None,
            "chapter_id": quiz.chapter_id if quiz else None,
            "score": r.score, "max_score": r.max_score,
            "percentage": round(100.0 * r.score / max(r.max_score, 1.0), 1),
            "time_taken_s": r.time_taken_s,
            "created_at": r.created_at.isoformat(),
        })
    return out


# ---------- Teacher analytics ----------

@router.get("/teacher/overview")
def teacher_overview(session: Session = Depends(get_session),
                     teacher: User = Depends(require_teacher)) -> dict:
    """Per-student attempt table: count and best percentage per student.

    Separate from dashboards.*/teacher/overview (which reports course
    ownership and pending queues) — this one is attempt-level.
    """
    students = session.exec(select(User).where(User.role == "student")
                            .order_by(User.id)).all()
    attempts = session.exec(select(QuizAttempt)).all()
    by_student: dict[int, list[QuizAttempt]] = {}
    for a in attempts:
        by_student.setdefault(a.user_id, []).append(a)

    def pct(a: QuizAttempt) -> float:
        return 100.0 * a.score / max(a.max_score, 1.0)

    per_student = []
    for s in students:
        mine = by_student.get(s.id, [])
        per_student.append({
            "id": s.id, "name": s.name, "email": s.email,
            "attempts": len(mine),
            "avg_score": round(sum(pct(a) for a in mine) / len(mine), 1) if mine else None,
        })
    overall = round(sum(pct(a) for a in attempts) / len(attempts), 1) if attempts else 0.0
    return {"students": per_student, "total_attempts": len(attempts),
            "overall_avg_score": overall}


# ---------- Teacher batches ----------

@router.post("/batches", status_code=201)
def create_batch(payload: BatchIn, session: Session = Depends(get_session),
                 teacher: User = Depends(require_teacher)) -> dict:
    """Create a class batch (group) owned by this teacher.

    The name is trimmed and must survive the trip — an all-whitespace name is
    rejected by the schema rather than stored as a blank row.
    """
    name = payload.name.strip()
    if not name:
        raise HTTPException(422, "name required")
    batch = Batch(name=name, description=payload.description, teacher_id=teacher.id)
    session.add(batch)
    session.commit()
    session.refresh(batch)
    return {"id": batch.id, "name": batch.name, "description": batch.description,
            "teacher_id": batch.teacher_id, "created_at": batch.created_at.isoformat()}
