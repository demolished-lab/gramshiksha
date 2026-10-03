import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import and_, or_, true
from sqlmodel import Session, select

from ..db import get_session
from ..models import MATERIAL_TYPES, Material, MaterialReport, User
from ..ratelimit import rate_limit
from ..security import get_current_user, has_role, require_any, require_roles
from ..storage import delete_ref, download_target, save_upload
from ..streams import stream_for
from .catalog import _check_stream, _stream_or_common

router = APIRouter(prefix="/materials", tags=["materials"])

ALLOWED_EXT = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg",
               ".jpeg": "image/jpeg", ".webp": "image/webp", ".mp3": "audio/mpeg",
               ".m4a": "audio/mp4", ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation"}
MAX_SIZE = 10 * 1024 * 1024  # 10 MB


def _save_file(file: UploadFile) -> tuple[str, int]:
    # Local disk by default; Cloudinary when CLOUDINARY_* env is set (see storage.py).
    return save_upload(file, ALLOWED_EXT, MAX_SIZE)


@router.post("", status_code=201)
def upload_material(
    _rl: None = Depends(rate_limit("materials.upload", 30)),
    title: str = Form(...),
    description: str = Form(""),
    type: str = Form("notes"),
    class_grade: int = Form(...),
    board: str = Form(...),
    subject_name: str = Form(...),
    chapter_title: str = Form(""),
    lang: str = Form("en"),
    visibility: str = Form("public"),
    source_of_content: str = Form("Created by teacher"),
    file: UploadFile = File(...),
    user: User = Depends(require_any),
    session: Session = Depends(get_session),
):
    if type not in MATERIAL_TYPES:
        raise HTTPException(422, f"type must be one of {MATERIAL_TYPES}")
    if visibility not in ("private", "school", "public"):
        raise HTTPException(422, "visibility must be private|school|public")
    # Students' uploads always start pending; approved teachers publish
    # immediately. A teacher still awaiting approval is treated like a
    # student — otherwise self-signup would be a shortcut past moderation.
    status = "pending" if user.role == "student" or user.role_status != "active" else "approved"
    if user.role == "student" and visibility == "public":
        visibility = "public"  # allowed, but gated behind approval
    path, size = _save_file(file)
    m = Material(
        title=title.strip(), description=description, type=type,
        class_grade=class_grade, board=board, subject_name=subject_name,
        stream=stream_for(class_grade, subject_name),
        chapter_title=chapter_title, lang=lang, uploader_id=user.id,
        uploader_role=user.role, visibility=visibility, status=status,
        source_of_content=source_of_content, file_path=path, file_size=size,
    )
    session.add(m)
    session.commit()
    session.refresh(m)
    return {"id": m.id, "status": m.status}


def _visible_query(user: User):
    """Approved materials this user may see: public, their own, or their
    school's. Used by BOTH the list and the download endpoint — previously
    download only checked `status`, so any authenticated user could pull
    another teacher's private file by guessing sequential IDs."""
    clauses = [Material.visibility == "public", Material.uploader_id == user.id]
    if user.school_id:
        clauses.append(and_(Material.visibility == "school",
                            User.school_id == user.school_id))
    return (select(Material)
            .join(User, User.id == Material.uploader_id, isouter=True)
            .where(Material.status == "approved", or_(*clauses)))


def _moderation_clause(user: User):
    """What a reviewer may act on: platform_admin sees everything; a school
    admin or teacher is confined to their own school (and their own uploads
    when they belong to no school). Moderation must not leak across schools."""
    if user.role == "platform_admin":
        return true()
    if user.school_id:
        return or_(Material.uploader_id == user.id, User.school_id == user.school_id)
    return Material.uploader_id == user.id


def _moderation_query(user: User):
    return (select(Material)
            .join(User, User.id == Material.uploader_id, isouter=True)
            .where(Material.status == "pending", _moderation_clause(user)))


@router.get("")
def list_materials(
    class_grade: Optional[int] = Query(None, ge=1, le=12),
    board: Optional[str] = None,
    subject_name: Optional[str] = None,
    type: Optional[str] = None,
    lang: Optional[str] = None,
    stream: str = "",
    mine: bool = False,
    limit: int = Query(20, le=100), offset: int = 0,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _check_stream(stream)
    if mine:
        rows = session.exec(select(Material).where(
            Material.uploader_id == user.id).order_by(Material.id.desc())
            .offset(offset).limit(limit)).all()
        return [_material_out(m, user) for m in rows]
    # Visibility is enforced in SQL too, so limit/offset paginate over the rows
    # the user can actually see (filtering after LIMIT pages over hidden rows).
    q = _visible_query(user)
    if class_grade:
        q = q.where(Material.class_grade == class_grade)
    if board:
        q = q.where(Material.board == board)
    if subject_name:
        q = q.where(Material.subject_name == subject_name)
    if type:
        q = q.where(Material.type == type)
    if lang:
        q = q.where(Material.lang == lang)
    if stream:
        q = q.where(_stream_or_common(Material.stream, stream))
    rows = session.exec(q.order_by(Material.id.desc()).offset(offset).limit(limit)).all()
    return [_material_out(m, user) for m in rows]


def _material_out(m: Material, user: User) -> dict:
    return {"id": m.id, "title": m.title, "description": m.description, "type": m.type,
            "class_grade": m.class_grade, "board": m.board, "subject_name": m.subject_name,
            "stream": m.stream,
            "chapter_title": m.chapter_title, "lang": m.lang, "status": m.status,
            "visibility": m.visibility, "source_of_content": m.source_of_content,
            "file_size": m.file_size, "downloads": m.downloads, "views": m.views,
            "mine": m.uploader_id == user.id, "created_at": m.created_at.isoformat()}


@router.get("/pending")
def pending_materials(user: User = Depends(require_roles("teacher", "school_admin", "platform_admin")),
                      session: Session = Depends(get_session)):
    # Scoped: teachers/school admins only see their own school's queue —
    # never another school's student uploads.
    rows = session.exec(_moderation_query(user).order_by(Material.id.desc())).all()
    return [_material_out(m, user) for m in rows]


@router.post("/{material_id}/review")
def review_material(material_id: int, decision: str = Form(...), reason: str = Form(""),
                    _rl: None = Depends(rate_limit("materials.review", 60)),
                    user: User = Depends(require_roles("teacher", "school_admin", "platform_admin")),
                    session: Session = Depends(get_session)):
    if decision not in ("approved", "needs_changes", "rejected"):
        raise HTTPException(422, "decision must be approved|needs_changes|rejected")
    # Same scope as the queue: a teacher can't approve another school's
    # material by posting its ID directly.
    m = session.exec(select(Material)
                     .join(User, User.id == Material.uploader_id, isouter=True)
                     .where(Material.id == material_id,
                            _moderation_clause(user))).first()
    if not m:
        raise HTTPException(404, "Material not found")
    m.status = decision
    m.review_reason = reason
    m.reviewer_id = user.id
    session.add(m)
    from ..models import Notification
    import json as _json
    session.add(Notification(user_id=m.uploader_id, type="material_review",
                             payload=_json.dumps({"material": m.title, "status": decision, "reason": reason})))
    session.commit()
    return {"ok": True, "status": m.status}


@router.get("/{material_id}/download")
def download_material(material_id: int, user: User = Depends(get_current_user),
                      session: Session = Depends(get_session)):
    # Same visibility rule as the list — approval alone is not enough to fetch.
    m = session.exec(_visible_query(user).where(Material.id == material_id)).first()
    if not m:
        raise HTTPException(404, "Material not found")
    kind, target = download_target(m.file_path)
    if kind == "redirect":
        # Cloudinary asset: approval/visibility already checked above;
        # redirect to a short-lived signed URL.
        m.downloads += 1
        session.add(m)
        session.commit()
        return RedirectResponse(target, status_code=302)
    if not os.path.exists(target):
        raise HTTPException(404, "File missing")
    m.downloads += 1
    session.add(m)
    session.commit()
    safe_name = f"{m.title[:40].strip()}_{os.path.basename(m.file_path)}"
    return FileResponse(target, filename=safe_name)


@router.post("/{material_id}/report", status_code=201)
def report_material(material_id: int, reason: str = Form(...), detail: str = Form(""),
                    _rl: None = Depends(rate_limit("materials.report", 10)),
                    user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    from ..models import REPORT_REASONS
    if reason not in REPORT_REASONS:
        raise HTTPException(422, f"reason must be one of {REPORT_REASONS}")
    # You can only report what you can see (no probing for private files).
    if not session.exec(_visible_query(user).where(Material.id == material_id)).first():
        raise HTTPException(404, "Material not found")
    session.add(MaterialReport(material_id=material_id, reporter_id=user.id,
                               reason=reason, detail=detail))
    session.commit()
    return {"ok": True}


@router.delete("/{material_id}")
def delete_material(material_id: int, user: User = Depends(get_current_user),
                    session: Session = Depends(get_session)):
    m = session.get(Material, material_id)
    if not m:
        raise HTTPException(404, "Material not found")
    if m.uploader_id != user.id and not has_role(user, "teacher", "school_admin", "platform_admin"):
        raise HTTPException(403, "Not allowed")
    delete_ref(m.file_path)  # local unlink or Cloudinary destroy (best-effort)
    session.delete(m)
    session.commit()
    return {"ok": True}
