import json
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..db import get_session
from ..models import (BadgeDef, Bookmark, Chapter, Course, DailyActivity, Doubt, Enrollment,
                      Lesson, Material, Note, Notification, PracticeAttempt, Progress, Question,
                      QuizAttempt, School, TopicStats, User, UserBadge, Certificate)
from ..security import get_current_user, require_roles

router = APIRouter(tags=["dashboards"])


# ---------- Student: progress + gamification ----------

@router.get("/progress/summary")
def progress_summary(user=Depends(require_roles("student")),
                     session: Session = Depends(get_session)):
    done = session.exec(select(Progress).where(
        Progress.user_id == user.id, Progress.completed == True)).all()  # noqa: E712
    attempts = session.exec(select(QuizAttempt).where(QuizAttempt.user_id == user.id)).all()
    avg = round(sum(a.score / max(a.max_score, 1) * 100 for a in attempts) / len(attempts), 1) if attempts else None
    week_ago = (date.today() - timedelta(days=7)).isoformat()
    acts = session.exec(select(DailyActivity).where(
        DailyActivity.user_id == user.id, DailyActivity.date >= week_ago)).all()
    badges = session.exec(select(UserBadge).where(UserBadge.user_id == user.id)).all()
    certs = session.exec(select(Certificate).where(Certificate.user_id == user.id)).all()
    return {
        "lessons_completed": len(done),
        "quizzes_taken": len(attempts),
        "quiz_avg_pct": avg,
        "week_minutes": sum(a.minutes for a in acts),
        "week_lessons": sum(a.lessons_completed for a in acts),
        "week_quizzes": sum(a.quizzes_taken for a in acts),
        "xp": user.xp, "streak_days": user.streak_days,
        "badges": badges_count(session, badges),
        "certificates": [{"cert_id": c.cert_id, "course_id": c.course_id,
                          "issued_at": c.issued_at.isoformat()} for c in certs],
    }


def badges_count(session, badges):
    out = []
    for b in badges:
        d = session.exec(select(BadgeDef).where(BadgeDef.code == b.badge_code)).first()
        out.append({"code": b.badge_code, "title_en": d.title_en if d else b.badge_code,
                    "awarded_at": b.awarded_at.isoformat()})
    return out


@router.get("/progress/weekly")
def progress_weekly(user=Depends(require_roles("student")),
                    session: Session = Depends(get_session)):
    start = (date.today() - timedelta(days=13)).isoformat()
    rows = session.exec(select(DailyActivity).where(
        DailyActivity.user_id == user.id, DailyActivity.date >= start)).all()
    by_date = {r.date: r.minutes for r in rows}
    days = [(date.today() - timedelta(days=i)).isoformat() for i in range(13, -1, -1)]
    return [{"date": d, "minutes": by_date.get(d, 0)} for d in days]


# ---------- Teacher: monitor ----------

@router.get("/teacher/students")
def teacher_students(user=Depends(require_roles("teacher", "school_admin", "platform_admin")),
                     session: Session = Depends(get_session)):
    students = session.exec(select(User).where(User.role == "student")).all()
    out = []
    for s in students:
        done = session.exec(select(Progress.id).where(
            Progress.user_id == s.id, Progress.completed == True)).all()  # noqa: E712
        attempts = session.exec(select(QuizAttempt).where(QuizAttempt.user_id == s.id)).all()
        avg = round(sum(a.score / max(a.max_score, 1) * 100 for a in attempts) / len(attempts), 1) if attempts else None
        weak = session.exec(select(TopicStats).where(
            TopicStats.user_id == s.id, TopicStats.attempted >= 5)).all()
        weak_list = [{"topic": w.topic, "subject": w.subject_name,
                      "accuracy_pct": round(100 * w.correct / w.attempted, 1)}
                     for w in weak if w.correct / w.attempted < 0.5]
        doubts = session.exec(select(Doubt).where(
            Doubt.student_id == s.id, Doubt.status == "pending")).all()
        out.append({"id": s.id, "name": s.name, "class_grade": s.class_grade,
                    "board": s.board, "lessons_completed": len(done),
                    "quizzes": len(attempts), "quiz_avg_pct": avg,
                    "weak_topics": weak_list, "pending_doubts": len(doubts),
                    "streak_days": s.streak_days, "xp": s.xp})
    return out


@router.get("/teacher/overview")
def teacher_overview(user=Depends(require_roles("teacher", "school_admin", "platform_admin")),
                     session: Session = Depends(get_session)):
    courses = session.exec(select(Course).where(Course.teacher_id == user.id)).all()
    pending = session.exec(select(Material).where(Material.status == "pending")).all()
    doubts = session.exec(select(Doubt).where(Doubt.status == "pending")).all()
    students = session.exec(select(User).where(User.role == "student")).all()
    return {"my_courses": [{"id": c.id, "title_en": c.title_en, "students": c.students_count}
                           for c in courses],
            "pending_material_reviews": len(pending),
            "pending_doubts": len(doubts),
            "total_students": len(students)}


# ---------- Parent ----------

@router.get("/parent/children")
def parent_children(user=Depends(require_roles("parent")),
                    session: Session = Depends(get_session)):
    # child users carry parent_of_id pointing at the parent's id
    children = session.exec(select(User).where(
        User.role == "student", User.parent_of_id == user.id)).all()
    out = []
    for c in children:
        week_ago = (date.today() - timedelta(days=7)).isoformat()
        acts = session.exec(select(DailyActivity).where(
            DailyActivity.user_id == c.id, DailyActivity.date >= week_ago)).all()
        attempts = session.exec(select(QuizAttempt).where(QuizAttempt.user_id == c.id)).all()
        avg = round(sum(a.score / max(a.max_score, 1) * 100 for a in attempts) / len(attempts), 1) if attempts else None
        done = session.exec(select(Progress.id).where(
            Progress.user_id == c.id, Progress.completed == True)).all()  # noqa: E712
        weak = session.exec(select(TopicStats).where(
            TopicStats.user_id == c.id, TopicStats.attempted >= 5)).all()
        weak_subjects = sorted({w.subject_name for w in weak if w.correct / w.attempted < 0.5})
        badges = session.exec(select(UserBadge).where(UserBadge.user_id == c.id)).all()
        certs = session.exec(select(Certificate).where(Certificate.user_id == c.id)).all()
        out.append({
            "id": c.id, "name": c.name, "class_grade": c.class_grade, "board": c.board,
            "lessons_completed": len(done),
            "week_minutes": sum(a.minutes for a in acts),
            "quiz_avg_pct": avg, "weak_subjects": weak_subjects,
            "streak_days": c.streak_days, "xp": c.xp, "badges": len(badges),
            "certificates": len(certs),
        })
    return out


@router.post("/parent/link")
def parent_link(child_email: str = Query(...), user=Depends(require_roles("parent")),
                session: Session = Depends(get_session)):
    child = session.exec(select(User).where(User.email == child_email)).first()
    if not child or child.role != "student":
        raise HTTPException(404, "Student not found")
    child.parent_of_id = user.id
    session.add(child)
    session.commit()
    return {"ok": True, "child": child.name}


# ---------- School admin ----------

@router.get("/school/stats")
def school_stats(user=Depends(require_roles("school_admin", "platform_admin")),
                 session: Session = Depends(get_session)):
    school_id = user.school_id
    students = session.exec(select(User).where(
        User.role == "student",
        User.school_id == school_id if school_id else User.id == User.id)).all()
    teachers = session.exec(select(User).where(User.role == "teacher")).all()
    total_done = 0
    for s in students:
        total_done += len(session.exec(select(Progress.id).where(
            Progress.user_id == s.id, Progress.completed == True)).all())  # noqa: E712
    return {"students": len(students), "teachers": len(teachers),
            "lessons_completed_total": total_done}


@router.post("/school/announce")
def school_announce(title: str = Query(...), body: str = Query(""),
                    user=Depends(require_roles("school_admin", "platform_admin")),
                    session: Session = Depends(get_session)):
    students = session.exec(select(User).where(User.role == "student")).all()
    for s in students:
        session.add(Notification(user_id=s.id, type="announcement",
                                 payload=json.dumps({"title": title, "body": body})))
    session.commit()
    return {"ok": True, "notified": len(students)}


# ---------- Platform admin ----------

@router.get("/admin/users")
def admin_users(role: Optional[str] = None, limit: int = 50, offset: int = 0,
                user=Depends(require_roles("platform_admin")),
                session: Session = Depends(get_session)):
    q = select(User)
    if role:
        q = q.where(User.role == role)
    rows = session.exec(q.offset(offset).limit(limit)).all()
    return [{"id": u.id, "email": u.email, "name": u.name, "role": u.role,
             "class_grade": u.class_grade, "board": u.board, "xp": u.xp} for u in rows]


@router.get("/admin/reports")
def admin_reports(user=Depends(require_roles("platform_admin", "school_admin", "teacher")),
                  session: Session = Depends(get_session)):
    from ..models import MaterialReport
    rows = session.exec(select(MaterialReport)).all()
    out = []
    for r in rows:
        m = session.get(Material, r.material_id)
        out.append({"id": r.id, "material_id": r.material_id,
                    "material_title": m.title if m else "?",
                    "reason": r.reason, "detail": r.detail,
                    "created_at": r.created_at.isoformat()})
    return out


# ---------- Search ----------

@router.get("/search")
def search(q: str = Query(..., min_length=2), class_grade: Optional[int] = None,
           board: Optional[str] = None, subject_name: Optional[str] = None,
           content_type: Optional[str] = None,
           session: Session = Depends(get_session),
           user=Depends(get_current_user)):
    results = {"courses": [], "lessons": [], "materials": [], "questions": []}
    like = f"%{q}%"
    cq = select(Course).where(Course.published == True)  # noqa: E712
    for c in session.exec(cq.limit(200)).all():
        if q.lower() in (c.title_en + c.title_hi + c.title_mr + c.desc_en).lower():
            if class_grade and c.class_grade != class_grade:
                continue
            results["courses"].append({"id": c.id, "title_en": c.title_en,
                                       "title_hi": c.title_hi, "class_grade": c.class_grade})
    lq = select(Lesson).where(Lesson.published == True)  # noqa: E712
    for l in session.exec(lq.limit(300)).all():
        if q.lower() in (l.title_en + l.title_hi + l.body_en).lower():
            results["lessons"].append({"id": l.id, "title_en": l.title_en, "title_hi": l.title_hi})
    mq = select(Material).where(Material.status == "approved")
    for m in session.exec(mq.limit(200)).all():
        if q.lower() in (m.title + m.description).lower():
            results["materials"].append({"id": m.id, "title": m.title, "type": m.type})
    for qq in session.exec(select(Question).limit(300)).all():
        if q.lower() in (qq.prompt_en + qq.prompt_hi).lower():
            results["questions"].append({"id": qq.id, "prompt_en": qq.prompt_en})
    if content_type:
        results = {content_type: results.get(content_type, [])}
    return results
