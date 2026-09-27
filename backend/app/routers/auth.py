from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select

from ..db import get_session
from ..gamification import seed_badges
from ..models import User
from ..security import create_access_token, get_current_user, hash_password, verify_password
from pydantic import BaseModel, EmailStr, Field

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=72)
    role: str = "student"
    lang_pref: str = "hi"
    class_grade: Optional[int] = Field(default=None, ge=1, le=12)
    board: Optional[str] = None
    school_name: str = ""


class ProfileUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=80)
    lang_pref: Optional[str] = None
    class_grade: Optional[int] = Field(default=None, ge=1, le=12)
    board: Optional[str] = None
    profile_pic: Optional[str] = None
    school_name: Optional[str] = None


class ResetRequest(BaseModel):
    email: EmailStr


class ResetConfirm(BaseModel):
    email: EmailStr
    new_password: str = Field(min_length=8, max_length=72)


@router.post("/register", status_code=201)
def register(payload: RegisterIn, session: Session = Depends(get_session)):
    from ..models import School

    if payload.role not in ("student", "teacher", "parent"):
        raise HTTPException(422, "Self-registration allowed for student, teacher, parent only")
    if session.exec(select(User).where(User.email == payload.email)).first():
        raise HTTPException(409, "Email already registered")

    school_id = None
    if payload.school_name.strip():
        school = session.exec(select(School).where(School.name == payload.school_name.strip())).first()
        if not school:
            school = School(name=payload.school_name.strip())
            session.add(school)
            session.flush()
        school_id = school.id

    user = User(
        email=payload.email,
        name=payload.name,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        lang_pref=payload.lang_pref if payload.lang_pref in ("en", "hi", "mr") else "hi",
        class_grade=payload.class_grade,
        board=payload.board,
        school_id=school_id,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    seed_badges(session)
    token = create_access_token(user.email, user.role)
    return {"id": user.id, "email": user.email, "name": user.name, "role": user.role,
            "access_token": token, "token_type": "bearer"}


@router.post("/token")
def login(form: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == form.username)).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(401, "Incorrect email or password")
    token = create_access_token(user.email, user.role)
    return {"access_token": token, "token_type": "bearer",
            "role": user.role, "name": user.name, "lang_pref": user.lang_pref,
            "class_grade": user.class_grade, "board": user.board, "xp": user.xp,
            "streak_days": user.streak_days}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "name": user.name, "role": user.role,
            "lang_pref": user.lang_pref, "class_grade": user.class_grade, "board": user.board,
            "school_id": user.school_id, "xp": user.xp, "streak_days": user.streak_days,
            "profile_pic": user.profile_pic}


@router.patch("/me")
def update_me(payload: ProfileUpdate, user: User = Depends(get_current_user),
              session: Session = Depends(get_session)):
    from ..models import School

    data = payload.model_dump(exclude_unset=True)
    school_name = data.pop("school_name", None)
    if school_name:
        school = session.exec(select(School).where(School.name == school_name.strip())).first()
        if not school:
            school = School(name=school_name.strip())
            session.add(school)
            session.flush()
        user.school_id = school.id
    if "lang_pref" in data and data["lang_pref"] not in ("en", "hi", "mr"):
        raise HTTPException(422, "lang must be en|hi|mr")
    for k, v in data.items():
        setattr(user, k, v)
    session.add(user)
    session.commit()
    return {"ok": True}


@router.post("/reset-request")
def reset_request(payload: ResetRequest, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == payload.email)).first()
    # Always 200 to avoid account enumeration
    if user:
        # v1: dev-friendly OTP-style code (prod: send via email/SMS gateway)
        code = str(int(datetime.now(timezone.utc).timestamp()))[-6:]
        user._reset_code = code  # type: ignore[attr-defined]
        import app.state_reset as rs
        rs.CODES[payload.email] = (code, datetime.now(timezone.utc) + timedelta(minutes=15))
    return {"ok": True, "code": rs.CODES.get(payload.email, (None, None))[0] if user else None}


@router.post("/reset-confirm")
def reset_confirm(payload: ResetConfirm, session: Session = Depends(get_session)):
    import app.state_reset as rs
    entry = rs.CODES.get(payload.email)
    if not entry or entry[1] < datetime.now(timezone.utc):
        raise HTTPException(400, "Invalid or expired code")
    user = session.exec(select(User).where(User.email == payload.email)).first()
    if not user:
        raise HTTPException(404, "User not found")
    user.hashed_password = hash_password(payload.new_password)
    session.add(user)
    session.commit()
    del rs.CODES[payload.email]
    return {"ok": True}
