import json
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr
from sqlalchemy import update as sqlalchemy_update
from sqlmodel import Session, select

from ..authorization import visible_students, visible_teacher_ids
from ..config import settings
from ..db import get_session
from ..models import (BadgeDef, Course, DailyActivity, Doubt, Lesson, Material, Notification, Progress, Question,
                      QuizAttempt, TopicStats, User, UserBadge, Certificate)
from ..security import get_current_user, require_roles

router = APIRouter(tags=["dashboards"])


class ParentInviteIn(BaseModel):
    parent_email: EmailStr


class ParentLinkIn(BaseModel):
    invite: str


class CourseTeacherIn(BaseModel):
    teacher_id: int


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
    students = visible_students(user, session)
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
    students = visible_students(user, session)
    student_ids = [s.id for s in students]
    teacher_ids = visible_teacher_ids(user, session)
    courses = session.exec(select(Course).where(Course.teacher_id.in_(teacher_ids))).all() if teacher_ids else []
    visible_uploader_ids = set(student_ids) | set(teacher_ids)
    if user.role == "platform_admin":
        pending = session.exec(select(Material).where(Material.status == "pending")).all()
        doubts = session.exec(select(Doubt).where(Doubt.status == "pending")).all()
    elif visible_uploader_ids:
        pending = session.exec(select(Material).where(
            Material.status == "pending", Material.uploader_id.in_(visible_uploader_ids))).all()
        doubts = session.exec(select(Doubt).where(
            Doubt.status == "pending", Doubt.student_id.in_(student_ids))).all() if student_ids else []
    else:
        pending, doubts = [], []
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


@router.post("/parent/invite")
def parent_invite(payload: ParentInviteIn, user=Depends(require_roles("student")),
                  session: Session = Depends(get_session)):
    if user.parent_of_id is not None:
        raise HTTPException(409, "A parent is already linked to this account")
    parent_email = str(payload.parent_email).strip().lower()
    parent = session.exec(select(User).where(User.email == parent_email)).first()
    if not parent or parent.role != "parent":
        raise HTTPException(404, "Create a parent account with this email before requesting an invite")
    now = datetime.now(timezone.utc)
    invite = jwt.encode({
        "sub": str(user.id), "parent_email": parent_email,
        "purpose": "parent_link", "iat": now,
        "exp": now + timedelta(minutes=30),
    }, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return {"invite": invite, "expires_in_seconds": 1800}


@router.post("/parent/link")
def parent_link(payload: ParentLinkIn, user=Depends(require_roles("parent")),
                session: Session = Depends(get_session)):
    try:
        claims = jwt.decode(payload.invite, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise HTTPException(400, "Invalid or expired student invitation")
    if claims.get("purpose") != "parent_link" or claims.get("parent_email") != user.email.strip().lower():
        raise HTTPException(400, "This invitation is not for your parent account")
    try:
        student_id = int(claims.get("sub", ""))
    except (TypeError, ValueError):
        raise HTTPException(400, "Invalid student invitation")
    child = session.get(User, student_id)
    if not child or child.role != "student":
        raise HTTPException(404, "Student not found")
    if child.parent_of_id is not None and child.parent_of_id != user.id:
        raise HTTPException(409, "This student already has a linked parent")
    if child.parent_of_id == user.id:
        return {"ok": True, "child": child.name}
    # Compare-and-set prevents concurrent invitations from replacing the first
    # accepted parent on databases where two requests race.
    updated = session.exec(sqlalchemy_update(User).where(
        User.id == student_id, User.role == "student", User.parent_of_id.is_(None)
    ).values(parent_of_id=user.id))
    if updated.rowcount != 1:
        session.rollback()
        current = session.get(User, student_id)
        if current and current.parent_of_id == user.id:
            return {"ok": True, "child": current.name}
        raise HTTPException(409, "This student already has a linked parent")
    session.commit()
    return {"ok": True, "child": child.name}


# ---------- School admin ----------

@router.get("/school/stats")
def school_stats(user=Depends(require_roles("school_admin", "platform_admin")),
                 session: Session = Depends(get_session)):
    students = visible_students(user, session)
    teacher_ids = visible_teacher_ids(user, session)
    total_done = 0
    for s in students:
        total_done += len(session.exec(select(Progress.id).where(
            Progress.user_id == s.id, Progress.completed == True)).all())  # noqa: E712
    return {"students": len(students), "teachers": len(teacher_ids),
            "lessons_completed_total": total_done}


@router.post("/school/announce")
def school_announce(title: str = Query(...), body: str = Query(""),
                    user=Depends(require_roles("school_admin", "platform_admin")),
                    session: Session = Depends(get_session)):
    students = visible_students(user, session)
    for s in students:
        session.add(Notification(user_id=s.id, type="announcement",
                                 payload=json.dumps({"title": title, "body": body})))
    session.commit()
    return {"ok": True, "notified": len(students)}


# ---------- Platform admin ----------

@router.get("/admin/users")
def admin_users(role: Optional[str] = None, limit: int = Query(50, ge=1, le=200),
                offset: int = Query(0, ge=0),
                user=Depends(require_roles("school_admin", "platform_admin")),
                session: Session = Depends(get_session)):
    q = select(User)
    if user.role == "school_admin":
        q = q.where(User.school_id == user.school_id) if user.school_id is not None else q.where(User.id == -1)
    if role:
        q = q.where(User.role == role)
    rows = session.exec(q.offset(offset).limit(limit)).all()
    return [{"id": u.id, "email": u.email, "name": u.name, "role": u.role,
             "role_status": u.role_status,
             "class_grade": u.class_grade, "board": u.board, "xp": u.xp} for u in rows]


def _require_not_self(target: User, actor: User) -> None:
    """Refuse changing your own approval status.

    The only account that can approve or suspend is a platform admin — so a
    self-suspend would leave the platform with nobody able to approve at all,
    requiring manual database surgery to recover.
    """
    if target.id == actor.id:
        raise HTTPException(400, "Cannot change your own approval status")


def _get_target(user_id: int, session: Session) -> User:
    target = session.get(User, user_id)
    if not target:
        raise HTTPException(404, "User not found")
    return target


@router.get("/admin/courses/assignable")
def assignable_courses(user=Depends(require_roles("school_admin", "platform_admin")),
                       session: Session = Depends(get_session)):
    if user.role == "platform_admin":
        rows = session.exec(select(Course).order_by(Course.id)).all()
    elif user.school_id is None:
        rows = []
    else:
        teacher_ids = visible_teacher_ids(user, session)
        q = select(Course)
        q = q.where(Course.teacher_id.in_(teacher_ids) | Course.teacher_id.is_(None)) if teacher_ids else q.where(Course.teacher_id.is_(None))
        rows = session.exec(q.order_by(Course.id)).all()
    return [{"id": course.id, "title_en": course.title_en,
             "class_grade": course.class_grade, "board": course.board,
             "teacher_id": course.teacher_id} for course in rows]


@router.post("/admin/courses/{course_id}/assign-teacher")
def assign_course_teacher(course_id: int, payload: CourseTeacherIn,
                          user=Depends(require_roles("school_admin", "platform_admin")),
                          session: Session = Depends(get_session)):
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(404, "Course not found")
    teacher = session.get(User, payload.teacher_id)
    if not teacher or teacher.role != "teacher" or teacher.role_status != "active":
        raise HTTPException(400, "Choose an approved teacher account")
    if user.role == "school_admin":
        current_owner = session.get(User, course.teacher_id) if course.teacher_id else None
        if (user.school_id is None or teacher.school_id != user.school_id
                or (current_owner and current_owner.school_id != user.school_id)):
            raise HTTPException(403, "You may only assign courses and teachers in your school")
    course.teacher_id = teacher.id
    session.add(course)
    session.commit()
    return {"ok": True, "course_id": course.id, "teacher_id": teacher.id}


def _set_status(target: User, status: str, session: Session) -> dict:
    target.role_status = status
    session.add(target)
    session.commit()
    session.refresh(target)
    return {"ok": True, "id": target.id, "email": target.email,
            "role": target.role, "role_status": target.role_status}


@router.post("/admin/users/{user_id}/approve")
def approve_user(user_id: int, user=Depends(require_roles("platform_admin")),
                 session: Session = Depends(get_session)):
    """Move a user out of `pending` (or back from `suspended`) — the step
    that actually grants the teacher role's privileges.

    Registration gives anyone the `teacher` *string*; publishing lessons,
    moderating material and reading student rosters are gated on approval.
    Idempotent: approving an already-active account is a no-op, not an error.
    """
    target = _get_target(user_id, session)
    _require_not_self(target, user)
    return _set_status(target, "active", session)


@router.post("/admin/users/{user_id}/suspend")
def suspend_user(user_id: int, user=Depends(require_roles("platform_admin")),
                 session: Session = Depends(get_session)):
    """Withdraw privileges without deleting the account.

    The counterweight to approve: approvals that were granted by mistake (or
    an account that turns out to be abusive) must be revocable, otherwise
    approval is a permanent grant. A suspended account keeps its login,
    coursework and uploaded files, but every privilege route refuses it with
    "Account suspended", and new uploads fall back into the review queue.
    Restoring is POST .../approve. Idempotent.
    """
    target = _get_target(user_id, session)
    _require_not_self(target, user)
    return _set_status(target, "suspended", session)


@router.get("/admin/reports")
def admin_reports(user=Depends(require_roles("platform_admin", "school_admin", "teacher")),
                  session: Session = Depends(get_session)):
    from ..models import MaterialReport
    if user.role == "platform_admin":
        rows = session.exec(select(MaterialReport)).all()
    elif user.role == "school_admin" and user.school_id is not None:
        school_user_ids = session.exec(select(User.id).where(User.school_id == user.school_id)).all()
        material_ids = session.exec(select(Material.id).where(Material.uploader_id.in_(school_user_ids))).all() if school_user_ids else []
        rows = session.exec(select(MaterialReport).where(MaterialReport.material_id.in_(material_ids))).all() if material_ids else []
    elif user.role == "teacher":
        material_ids = session.exec(select(Material.id).where(Material.uploader_id == user.id)).all()
        rows = session.exec(select(MaterialReport).where(MaterialReport.material_id.in_(material_ids))).all() if material_ids else []
    else:
        rows = []
    out = []
    for r in rows:
        m = session.get(Material, r.material_id)
        out.append({"id": r.id, "material_id": r.material_id,
                    "material_title": m.title if m else "?",
                    "reason": r.reason, "detail": r.detail,
                    "created_at": r.created_at.isoformat()})
    return out


@router.post("/admin/textbooks/recheck")
def recheck_textbooks(limit: int = Query(50, ge=1, le=200),
                      only_unchecked: bool = Query(True),
                      user=Depends(require_roles("platform_admin")),
                      session: Session = Depends(get_session)):
    """Link-health pass over textbook deep_urls (sequential + polite, no burst).
    Updates last_checked/last_ok so /open auto-falls-back on dead PDFs."""
    from ..models import Textbook, utcnow
    from ..routers.catalog import check_url
    q = select(Textbook).where(Textbook.deep_url != "")
    if only_unchecked:
        q = q.where(Textbook.last_checked.is_(None))
    rows = session.exec(q.limit(limit)).all()
    checked = ok = 0
    for t in rows:
        good = check_url(t.deep_url)
        t.last_ok = good
        t.last_checked = utcnow().isoformat()
        session.add(t)
        checked += 1
        ok += int(good)
    session.commit()
    return {"checked": checked, "ok": ok, "dead": checked - ok}


# ---------- Search ----------

@router.get("/search")
def search(q: str = Query(..., min_length=2, max_length=100), class_grade: Optional[int] = None,
           board: Optional[str] = None, subject_name: Optional[str] = None,
           content_type: Optional[str] = None, limit: int = Query(20, ge=1, le=50),
           session: Session = Depends(get_session),
           user=Depends(get_current_user)):
    results = {"courses": [], "lessons": [], "materials": [], "questions": []}
    cq = select(Course).where(Course.published == True)  # noqa: E712
    for c in session.exec(cq.limit(200)).all():
        if q.lower() in (c.title_en + c.title_hi + c.title_mr + c.desc_en).lower():
            if class_grade and c.class_grade != class_grade:
                continue
            results["courses"].append({"id": c.id, "title_en": c.title_en,
                                       "title_hi": c.title_hi, "class_grade": c.class_grade})
            if len(results["courses"]) >= limit:
                break
    lq = select(Lesson).where(Lesson.published == True)  # noqa: E712
    for les in session.exec(lq.limit(300)).all():
        if q.lower() in (les.title_en + les.title_hi + les.body_en).lower():
            results["lessons"].append({"id": les.id, "title_en": les.title_en, "title_hi": les.title_hi})
            if len(results["lessons"]) >= limit:
                break
    mq = select(Material).where(Material.status == "approved")
    for m in session.exec(mq.limit(200)).all():
        if q.lower() in (m.title + m.description).lower():
            results["materials"].append({"id": m.id, "title": m.title, "type": m.type})
            if len(results["materials"]) >= limit:
                break
    for qq in session.exec(select(Question).limit(300)).all():
        if q.lower() in (qq.prompt_en + qq.prompt_hi).lower():
            results["questions"].append({"id": qq.id, "prompt_en": qq.prompt_en})
            if len(results["questions"]) >= limit:
                break
    if content_type:
        results = {content_type: results.get(content_type, [])}
    return results
