from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..db import get_session
from ..models import Batch, Progress, QuizAttempt, User
from ..schemas import ProgressOut
from ..security import get_current_user, require_teacher

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("/me", response_model=list[ProgressOut])
def my_progress(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[ProgressOut]:
    rows = session.exec(select(Progress).where(Progress.user_id == user.id)).all()
    return [ProgressOut.model_validate(r) for r in rows]


@router.get("/me/attempts")
def my_attempts(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[dict]:
    rows = session.exec(
        select(QuizAttempt).where(QuizAttempt.user_id == user.id).order_by(QuizAttempt.created_at.desc())
    ).all()
    return [
        {"id": r.id, "lesson_id": r.lesson_id, "score": r.score, "created_at": r.created_at.isoformat()}
        for r in rows
    ]


# --- Teacher analytics ---

@router.get("/teacher/overview")
def teacher_overview(
    session: Session = Depends(get_session),
    teacher: User = Depends(require_teacher),
) -> dict:
    students = session.exec(select(User).where(User.role == "student")).all()
    attempts = session.exec(select(QuizAttempt)).all()
    per_student = []
    for s in students:
        s_attempts = [a for a in attempts if a.user_id == s.id]
        avg = round(sum(a.score for a in s_attempts) / len(s_attempts), 2) if s_attempts else None
        per_student.append(
            {
                "id": s.id,
                "name": s.name,
                "email": s.email,
                "attempts": len(s_attempts),
                "avg_score": avg,
            }
        )
    overall_avg = round(sum(a.score for a in attempts) / len(attempts), 2) if attempts else None
    return {"students": per_student, "total_attempts": len(attempts), "overall_avg_score": overall_avg}


@router.post("/batches", status_code=201)
def create_batch(
    name: str,
    description: str = "",
    session: Session = Depends(get_session),
    teacher: User = Depends(require_teacher),
) -> dict:
    if not name.strip():
        raise HTTPException(status_code=422, detail="name required")
    b = Batch(name=name.strip(), description=description, teacher_id=teacher.id)
    session.add(b)
    session.commit()
    session.refresh(b)
    return {"id": b.id, "name": b.name}

