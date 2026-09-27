import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from ..db import get_session
from ..models import MATERIAL_STATUSES, MATERIAL_TYPES, Material, MaterialReport, User
from ..security import get_current_user, require_any, require_roles

router = APIRouter(prefix="/materials", tags=["materials"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads")
ALLOWED_EXT = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg",
               ".jpeg": "image/jpeg", ".webp": "image/webp", ".mp3": "audio/mpeg",
               ".m4a": "audio/mp4", ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation"}
MAX_SIZE = 10 * 1024 * 1024  # 10 MB


def _save_file(file: UploadFile) -> tuple[str, int]:
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(422, f"File type {ext or '(none)'} not allowed. Allowed: {sorted(ALLOWED_EXT)}")
    data = file.file.read(MAX_SIZE + 1)
    if len(data) > MAX_SIZE:
        raise HTTPException(422, "File too large (max 10 MB)")
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    name = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(UPLOAD_DIR, name)
    with open(path, "wb") as f:
        f.write(data)
    return f"uploads/{name}", len(data)


@router.post("", status_code=201)
def upload_material(
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
    # Students' uploads always start pending; teacher uploads are approved automatically.
    status = "pending" if user.role == "student" else "approved"
    if user.role == "student" and visibility == "public":
        visibility = "public"  # allowed, but gated behind approval
    path, size = _save_file(file)
    m = Material(
        title=title.strip(), description=description, type=type,
        class_grade=class_grade, board=board, subject_name=subject_name,
        chapter_title=chapter_title, lang=lang, uploader_id=user.id,
        uploader_role=user.role, visibility=visibility, status=status,
        source_of_content=source_of_content, file_path=path, file_size=size,
    )
    session.add(m)
    session.commit()
    session.refresh(m)
    return {"id": m.id, "status": m.status}


def _visible_to(user: User) -> list:
    """Public approved + own uploads + school-scoped if user has a school."""
    conds = [Material.status == "approved"]
    # visibility filter applied in python for simplicity of three-way scope
    return conds


@router.get("")
def list_materials(
    class_grade: Optional[int] = Query(None, ge=1, le=12),
    board: Optional[str] = None,
    subject_name: Optional[str] = None,
    type: Optional[str] = None,
    lang: Optional[str] = None,
    mine: bool = False,
    limit: int = Query(20, le=100), offset: int = 0,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if mine:
        rows = session.exec(select(Material).where(
            Material.uploader_id == user.id).offset(offset).limit(limit)).all()
        return [_material_out(m, user) for m in rows]
    rows = session.exec(select(Material).where(
        Material.status == "approved").offset(offset).limit(limit)).all()
    out = []
    for m in rows:
        if m.visibility == "public":
            ok = True
        elif m.visibility == "school":
            ok = m.uploader_id == user.id or (user.school_id and _uploader_school(session, m) == user.school_id)
        else:  # private
            ok = m.uploader_id == user.id
        if not ok:
            continue
        item = _material_out(m, user)
        if class_grade and m.class_grade != class_grade:
            continue
        if board and m.board != board:
            continue
        if subject_name and m.subject_name != subject_name:
            continue
        if type and m.type != type:
            continue
        if lang and m.lang != lang:
            continue
        out.append(item)
    return out


def _uploader_school(session: Session, m: Material):
    u = session.get(User, m.uploader_id)
    return u.school_id if u else None


def _material_out(m: Material, user: User) -> dict:
    return {"id": m.id, "title": m.title, "description": m.description, "type": m.type,
            "class_grade": m.class_grade, "board": m.board, "subject_name": m.subject_name,
            "chapter_title": m.chapter_title, "lang": m.lang, "status": m.status,
            "visibility": m.visibility, "source_of_content": m.source_of_content,
            "file_size": m.file_size, "downloads": m.downloads, "views": m.views,
            "mine": m.uploader_id == user.id, "created_at": m.created_at.isoformat()}


@router.get("/pending")
def pending_materials(user: User = Depends(require_roles("teacher", "school_admin", "platform_admin")),
                      session: Session = Depends(get_session)):
    rows = session.exec(select(Material).where(Material.status == "pending")).all()
    if user.role == "teacher":
        # teachers review only their school scope or own; simplified: all pending for teachers in v1
        pass
    return [_material_out(m, user) for m in rows]


@router.post("/{material_id}/review")
def review_material(material_id: int, decision: str = Form(...), reason: str = Form(""),
                    user: User = Depends(require_roles("teacher", "school_admin", "platform_admin")),
                    session: Session = Depends(get_session)):
    if decision not in ("approved", "needs_changes", "rejected"):
        raise HTTPException(422, "decision must be approved|needs_changes|rejected")
    m = session.get(Material, material_id)
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
    m = session.get(Material, material_id)
    if not m or m.status != "approved":
        raise HTTPException(404, "Material not found")
    full = os.path.join(os.path.dirname(UPLOAD_DIR), m.file_path.replace("/", os.sep))
    if not os.path.exists(full):
        raise HTTPException(404, "File missing")
    m.downloads += 1
    session.add(m)
    session.commit()
    safe_name = f"{m.title[:40].strip()}_{os.path.basename(m.file_path)}"
    return FileResponse(full, filename= safe_name)


@router.post("/{material_id}/report", status_code=201)
def report_material(material_id: int, reason: str = Form(...), detail: str = Form(""),
                    user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    from ..models import REPORT_REASONS
    if reason not in REPORT_REASONS:
        raise HTTPException(422, f"reason must be one of {REPORT_REASONS}")
    if not session.get(Material, material_id):
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
    if m.uploader_id != user.id and user.role not in ("teacher", "school_admin", "platform_admin"):
        raise HTTPException(403, "Not allowed")
    full = os.path.join(os.path.dirname(UPLOAD_DIR), m.file_path.replace("/", os.sep))
    if os.path.exists(full):
        os.remove(full)
    session.delete(m)
    session.commit()
    return {"ok": True}
