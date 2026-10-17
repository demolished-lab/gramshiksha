"""Tenant-aware helpers for student and teacher analytics visibility."""
from sqlmodel import Session, select

from .models import Course, Enrollment, User


def visible_students(user: User, session: Session) -> list[User]:
    """Return only learners an actor is authorized to monitor.

    Platform admins are global. School admins are limited to their assigned
    school (an unassigned admin sees nothing). Teachers see only learners who
    enrolled in one of their owned courses; a teacher without courses sees no
    student records.
    """
    query = select(User).where(User.role == "student")
    if user.role == "platform_admin":
        return list(session.exec(query.order_by(User.id)).all())
    if user.role == "school_admin":
        if user.school_id is None:
            return []
        return list(session.exec(query.where(User.school_id == user.school_id).order_by(User.id)).all())
    if user.role != "teacher":
        return []

    course_ids = session.exec(select(Course.id).where(Course.teacher_id == user.id)).all()
    if not course_ids:
        return []
    student_ids = session.exec(select(Enrollment.user_id).where(Enrollment.course_id.in_(course_ids))).all()
    if not student_ids:
        return []
    return list(session.exec(query.where(User.id.in_(set(student_ids))).order_by(User.id)).all())


def visible_teacher_ids(user: User, session: Session) -> list[int]:
    """Return teacher ids visible to an admin; teachers only see themselves."""
    if user.role == "platform_admin":
        return list(session.exec(select(User.id).where(User.role == "teacher")).all())
    if user.role == "school_admin" and user.school_id is not None:
        return list(session.exec(select(User.id).where(
            User.role == "teacher", User.school_id == user.school_id)).all())
    if user.role == "teacher":
        return [user.id] if user.id is not None else []
    return []
