from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..db import get_session
from ..models import (Bookmark, Doubt, DoubtReply, Lesson, Note, Notification, User, utcnow)
from ..ratelimit import rate_limit
from ..security import get_current_user, require_roles

router = APIRouter(tags=["social"])


# ---------- Doubts ----------

class DoubtIn(BaseModel):
    subject_name: str = "general"
    chapter_title: str = ""
    text: str = Field(min_length=5, max_length=2000)


@router.post("/doubts", status_code=201,
             dependencies=[Depends(rate_limit("doubts.create", 30))])
def ask_doubt(payload: DoubtIn, user=Depends(require_roles("student")),
              session: Session = Depends(get_session)):
    d = Doubt(student_id=user.id, subject_name=payload.subject_name,
              chapter_title=payload.chapter_title, text=payload.text.strip())
    session.add(d)
    session.commit()
    session.refresh(d)
    return {"id": d.id, "status": d.status}


@router.get("/doubts")
def my_doubts(user=Depends(get_current_user), session: Session = Depends(get_session)):
    if user.role == "student":
        rows = session.exec(select(Doubt).where(Doubt.student_id == user.id)).all()
    else:
        rows = session.exec(select(Doubt).order_by(Doubt.created_at.desc())).all()
    out = []
    for d in rows:
        student = session.get(User, d.student_id)
        replies = session.exec(select(DoubtReply).where(DoubtReply.doubt_id == d.id)).all()
        out.append({
            "id": d.id, "text": d.text, "subject_name": d.subject_name,
            "chapter_title": d.chapter_title, "status": d.status,
            "created_at": d.created_at.isoformat(),
            "student_name": student.name if student else "?",
            "replies": [{"teacher_id": r.teacher_id, "body": r.body,
                         "created_at": r.created_at.isoformat()} for r in replies],
        })
    return out


class ReplyIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


@router.post("/doubts/{doubt_id}/reply", status_code=201,
             dependencies=[Depends(rate_limit("doubts.reply", 60))])
def reply_doubt(doubt_id: int, payload: ReplyIn,
                user=Depends(require_roles("teacher", "school_admin", "platform_admin")),
                session: Session = Depends(get_session)):
    d = session.get(Doubt, doubt_id)
    if not d:
        raise HTTPException(404, "Doubt not found")
    session.add(DoubtReply(doubt_id=doubt_id, teacher_id=user.id, body=payload.body))
    d.status = "answered"
    session.add(d)
    session.add(Notification(user_id=d.student_id, type="doubt_answered",
                             payload=f'{{"doubt_id": {doubt_id}}}'))
    session.commit()
    return {"ok": True}


@router.post("/doubts/{doubt_id}/resolve")
def resolve_doubt(doubt_id: int, user=Depends(get_current_user),
                  session: Session = Depends(get_session)):
    d = session.get(Doubt, doubt_id)
    if not d:
        raise HTTPException(404, "Doubt not found")
    if d.student_id != user.id and user.role not in ("teacher", "school_admin", "platform_admin"):
        raise HTTPException(403, "Not allowed")
    d.status = "resolved"
    session.add(d)
    session.commit()
    return {"ok": True}


# ---------- Bookmarks ----------

@router.post("/bookmarks", status_code=201)
def add_bookmark(lesson_id: Optional[int] = None, course_id: Optional[int] = None,
                 question_id: Optional[int] = None,
                 user=Depends(get_current_user), session: Session = Depends(get_session)):
    if not (lesson_id or course_id or question_id):
        raise HTTPException(422, "Provide lesson_id, course_id or question_id")
    session.add(Bookmark(user_id=user.id, lesson_id=lesson_id,
                         course_id=course_id, question_id=question_id))
    session.commit()
    return {"ok": True}


@router.get("/bookmarks")
def list_bookmarks(user=Depends(get_current_user), session: Session = Depends(get_session)):
    rows = session.exec(select(Bookmark).where(Bookmark.user_id == user.id)).all()
    out = []
    for b in rows:
        out.append({"id": b.id, "lesson_id": b.lesson_id, "course_id": b.course_id,
                    "question_id": b.question_id})
    return out


@router.delete("/bookmarks/{bookmark_id}")
def del_bookmark(bookmark_id: int, user=Depends(get_current_user),
                 session: Session = Depends(get_session)):
    b = session.get(Bookmark, bookmark_id)
    if not b or b.user_id != user.id:
        raise HTTPException(404, "Bookmark not found")
    session.delete(b)
    session.commit()
    return {"ok": True}


# ---------- Notes ----------

class NoteIn(BaseModel):
    lesson_id: int
    body: str = Field(min_length=1, max_length=5000)


@router.post("/notes", status_code=201,
             dependencies=[Depends(rate_limit("notes.create", 60))])
def add_note(payload: NoteIn, user=Depends(get_current_user),
             session: Session = Depends(get_session)):
    n = Note(user_id=user.id, lesson_id=payload.lesson_id, body=payload.body)
    session.add(n)
    session.commit()
    session.refresh(n)
    return {"id": n.id}


@router.get("/notes")
def list_notes(lesson_id: Optional[int] = None, user=Depends(get_current_user),
               session: Session = Depends(get_session)):
    q = select(Note).where(Note.user_id == user.id)
    if lesson_id:
        q = q.where(Note.lesson_id == lesson_id)
    rows = session.exec(q).all()
    return [{"id": n.id, "lesson_id": n.lesson_id, "body": n.body,
             "created_at": n.created_at.isoformat()} for n in rows]


@router.patch("/notes/{note_id}")
def edit_note(note_id: int, payload: NoteIn, user=Depends(get_current_user),
              session: Session = Depends(get_session)):
    n = session.get(Note, note_id)
    if not n or n.user_id != user.id:
        raise HTTPException(404, "Note not found")
    n.body = payload.body
    session.add(n)
    session.commit()
    return {"ok": True}


@router.delete("/notes/{note_id}")
def del_note(note_id: int, user=Depends(get_current_user),
             session: Session = Depends(get_session)):
    n = session.get(Note, note_id)
    if not n or n.user_id != user.id:
        raise HTTPException(404, "Note not found")
    session.delete(n)
    session.commit()
    return {"ok": True}


# ---------- Notifications ----------

@router.get("/notifications")
def list_notifications(user=Depends(get_current_user), session: Session = Depends(get_session)):
    rows = session.exec(select(Notification).where(
        Notification.user_id == user.id).order_by(Notification.created_at.desc())).all()
    import json as _json
    return [{"id": n.id, "type": n.type, "payload": _json.loads(n.payload or "{}"),
             "read": n.read, "created_at": n.created_at.isoformat()} for n in rows]


@router.post("/notifications/read-all")
def read_all(user=Depends(get_current_user), session: Session = Depends(get_session)):
    rows = session.exec(select(Notification).where(
        Notification.user_id == user.id, Notification.read == False)).all()  # noqa: E712
    for n in rows:
        n.read = True
        session.add(n)
    session.commit()
    return {"ok": True, "marked": len(rows)}
