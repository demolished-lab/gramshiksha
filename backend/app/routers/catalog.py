from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from ..db import get_session
from ..models import Board, Course, Enrollment, Subject, Textbook, User
from ..security import get_current_user, require_student

router = APIRouter(tags=["catalog"])


@router.get("/meta/boards")
def list_boards(session: Session = Depends(get_session)):
    rows = session.exec(select(Board)).all()
    return [{"id": b.id, "name": b.name} for b in rows] or [
        {"id": 1, "name": "Maharashtra SSC"}, {"id": 2, "name": "Maharashtra HSC"},
        {"id": 3, "name": "CBSE"}]


@router.get("/meta/subjects")
def list_subjects(class_grade: int = Query(..., ge=1, le=12), board: str = Query("CBSE"),
                  session: Session = Depends(get_session)):
    rows = session.exec(select(Subject).where(
        Subject.class_grade == class_grade, Subject.board == board)).all()
    return [{"id": s.id, "name_en": s.name_en, "name_hi": s.name_hi, "name_mr": s.name_mr}
            for s in rows]


@router.get("/courses")
def list_courses(
    class_grade: Optional[int] = Query(None, ge=1, le=12),
    board: Optional[str] = None,
    subject_id: Optional[int] = None,
    lang: Optional[str] = None,
    difficulty: Optional[str] = None,
    free_only: bool = False,
    sort: str = Query("popular", pattern="^(popular|newest|rating|shortest|longest)$"),
    limit: int = Query(20, le=100),
    offset: int = 0,
    session: Session = Depends(get_session),
):
    q = select(Course).where(Course.published == True)  # noqa: E712
    if class_grade:
        q = q.where(Course.class_grade == class_grade)
    if board:
        q = q.where(Course.board == board)
    if subject_id:
        q = q.where(Course.subject_id == subject_id)
    if lang:
        q = q.where(Course.lang == lang)
    if difficulty:
        q = q.where(Course.difficulty == difficulty)
    if free_only:
        q = q.where(Course.is_free == True)  # noqa: E712
    order = {
        "popular": Course.students_count.desc(),
        "newest": Course.created_at.desc(),
        "rating": Course.rating.desc(),
        "shortest": Course.duration_min.asc(),
        "longest": Course.duration_min.desc(),
    }[sort]
    rows = session.exec(q.order_by(order).offset(offset).limit(limit)).all()
    total = len(rows)
    return {"total": total, "items": [_course_out(c) for c in rows]}


def _course_out(c: Course) -> dict:
    return {
        "id": c.id, "slug": c.slug, "title_en": c.title_en, "title_hi": c.title_hi,
        "title_mr": c.title_mr, "desc_en": c.desc_en, "desc_hi": c.desc_hi,
        "desc_mr": c.desc_mr, "board": c.board, "class_grade": c.class_grade,
        "subject_id": c.subject_id, "lang": c.lang, "difficulty": c.difficulty,
        "duration_min": c.duration_min, "rating": c.rating,
        "ratings_count": c.ratings_count, "students_count": c.students_count,
        "is_free": c.is_free, "thumb_color": c.thumb_color, "teacher_id": c.teacher_id,
    }


@router.get("/courses/{course_id}")
def get_course(course_id: int, session: Session = Depends(get_session)):
    c = session.get(Course, course_id)
    if not c or not c.published:
        raise HTTPException(404, "Course not found")
    from ..models import Chapter, Lesson
    chapters = session.exec(select(Chapter).where(
        Chapter.course_id == course_id).order_by(Chapter.order)).all()
    out = _course_out(c)
    chs = []
    for ch in chapters:
        lessons = session.exec(
            select(Lesson).where(
                Lesson.chapter_id == ch.id, Lesson.published == True)  # noqa: E712
            .order_by(Lesson.order)).all()
        chs.append({
            "id": ch.id, "order": ch.order, "title_en": ch.title_en,
            "title_hi": ch.title_hi, "title_mr": ch.title_mr,
            "lessons": [{"id": l.id, "order": l.order, "type": l.type,
                         "title_en": l.title_en, "title_hi": l.title_hi,
                         "title_mr": l.title_mr, "duration_min": l.duration_min,
                         "estimate_mb": l.estimate_mb} for l in lessons],
        })
    out["chapters"] = chs
    return out


@router.post("/courses/{course_id}/enroll", status_code=201)
def enroll(course_id: int, user: User = Depends(require_student),
           session: Session = Depends(get_session)):
    if not session.get(Course, course_id):
        raise HTTPException(404, "Course not found")
    existing = session.exec(select(Enrollment).where(
        Enrollment.user_id == user.id, Enrollment.course_id == course_id)).first()
    if existing:
        return {"ok": True, "already": True}
    session.add(Enrollment(user_id=user.id, course_id=course_id))
    course = session.get(Course, course_id)
    if course:
        course.students_count += 1
        session.add(course)
    session.commit()
    return {"ok": True}


@router.get("/my/courses")
def my_courses(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    rows = session.exec(select(Enrollment).where(Enrollment.user_id == user.id)).all()
    out = []
    for e in rows:
        c = session.get(Course, e.course_id)
        if c:
            item = _course_out(c)
            item["progress_pct"] = e.progress_pct
            out.append(item)
    return out


@router.get("/textbooks")
def textbooks(class_grade: int = Query(..., ge=1, le=12), board: str = Query(...),
              subject_name: Optional[str] = None, lang: Optional[str] = None,
              session: Session = Depends(get_session)):
    q = select(Textbook).where(Textbook.class_grade == class_grade, Textbook.board == board)
    if subject_name:
        q = q.where(Textbook.subject_name == subject_name)
    if lang:
        q = q.where(Textbook.lang == lang)
    rows = session.exec(q).all()
    return [{"id": t.id, "title": t.title, "board": t.board, "class_grade": t.class_grade,
             "subject_name": t.subject_name, "lang": t.lang, "source_url": t.source_url,
             "publisher": t.publisher} for t in rows]
