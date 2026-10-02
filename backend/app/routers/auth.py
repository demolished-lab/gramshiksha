from datetime import datetime, timedelta, timezone
from typing import Optional
import hashlib
import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select

from ..config import settings
from ..db import get_session
from ..gamification import seed_badges
from ..mailer import send_reset_email
from ..models import PasswordResetCode, User
# NOT dead code: tests clear the limiter and read its config through this
# module (auth_router._RATE / auth_router.RATE_LIMIT) — keep the aliases.
from ..ratelimit import DEFAULT_LIMIT as RATE_LIMIT, DEFAULT_WINDOW_S as RATE_WINDOW_S  # noqa: F401
from ..ratelimit import HITS as _RATE  # noqa: F401
from ..ratelimit import check as _check_rate
from ..security import create_access_token, get_current_user, hash_password, verify_password
from pydantic import BaseModel, EmailStr, Field

log = logging.getLogger("gramshiksha")

router = APIRouter(prefix="/auth", tags=["auth"])

RESET_TTL_MIN = 15  # reset codes live 15 minutes


class RegisterIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=72)
    role: str = "student"
    lang_pref: str = "hi"
    class_grade: Optional[int] = Field(default=None, ge=1, le=12)
    board: Optional[str] = None
    school_name: str = ""
    # Invite code ("GS000123") captured from ?ref= by the frontend. Unknown
    # or garbage codes are ignored — registration never fails over them.
    ref: str = ""


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
    code: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=8, max_length=72)


def _hash_code(email: str, code: str) -> str:
    # Salted per account so a DB dump can't be rainbow-tabled back to codes.
    return hashlib.sha256(f"{email.strip().lower()}:{code}".encode()).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.post("/register", status_code=201)
def register(payload: RegisterIn, request: Request, session: Session = Depends(get_session)):
    from ..models import School

    _check_rate(request, "register")
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
        # Anyone may type "teacher" at signup, so the role alone must not
        # confer anything: teachers start pending until a platform admin
        # approves them (POST /admin/users/{id}/approve).
        role_status="pending" if payload.role == "teacher" else "active",
        lang_pref=payload.lang_pref if payload.lang_pref in ("en", "hi", "mr") else "hi",
        class_grade=payload.class_grade,
        board=payload.board,
        school_id=school_id,
    )
    if settings.referral_enabled and payload.ref.strip():
        from .growth import resolve_referrer
        referrer = resolve_referrer(payload.ref, session)
        if referrer is not None:
            user.referred_by = referrer.id
    session.add(user)
    session.commit()
    session.refresh(user)
    seed_badges(session)
    token = create_access_token(user.email, user.role)
    return {"id": user.id, "email": user.email, "name": user.name, "role": user.role,
            "role_status": user.role_status,
            "access_token": token, "token_type": "bearer"}


@router.post("/token")
def login(request: Request, form: OAuth2PasswordRequestForm = Depends(),
          session: Session = Depends(get_session)):
    _check_rate(request, "token")
    user = session.exec(select(User).where(User.email == form.username)).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(401, "Incorrect email or password")
    return _login_payload(user)


def _login_payload(user: User) -> dict:
    token = create_access_token(user.email, user.role)
    # role_status rides on the login response so the UI can render the
    # pending/suspended notice immediately, without a second /auth/me round
    # trip that would first show the privileged page and then its 403.
    return {"access_token": token, "token_type": "bearer",
            "role": user.role, "role_status": user.role_status,
            "name": user.name, "lang_pref": user.lang_pref,
            "class_grade": user.class_grade, "board": user.board, "xp": user.xp,
            "streak_days": user.streak_days}


def _role_login(request: Request, form: OAuth2PasswordRequestForm,
                session: Session, role: str, rate_key: str) -> dict:
    """Designated login for one role only (teacher / student pages).

    Wrong password (or unknown email) is always 401 with no role hint — the
    403 names the expected role only after the password verified, at which
    point the caller already owns the credential and /token would have told
    them the role anyway."""
    _check_rate(request, rate_key)
    user = session.exec(select(User).where(User.email == form.username)).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(401, "Incorrect email or password")
    if user.role != role:
        raise HTTPException(
            403, f"This login page is for {role}s — this account is a {user.role}")
    return _login_payload(user)


@router.post("/token/teacher")
def login_teacher(request: Request, form: OAuth2PasswordRequestForm = Depends(),
                  session: Session = Depends(get_session)):
    return _role_login(request, form, session, "teacher", "token.teacher")


@router.post("/token/student")
def login_student(request: Request, form: OAuth2PasswordRequestForm = Depends(),
                  session: Session = Depends(get_session)):
    return _role_login(request, form, session, "student", "token.student")


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "name": user.name, "role": user.role,
            "role_status": user.role_status,
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
def reset_request(payload: ResetRequest, request: Request, session: Session = Depends(get_session)):
    _check_rate(request, "reset-request")
    # Answer *before* touching the account: if the server can't deliver codes
    # at all, every address must get the identical response, or the status
    # code itself would reveal which accounts exist.
    if settings.is_production and not settings.smtp_enabled:
        log.error("Password reset unavailable: SMTP not configured "
                  "(set SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASSWORD).")
        raise HTTPException(503, "Password reset is temporarily unavailable. "
                                 "Please ask your school administrator to reset your password.")

    # Always the same 200 shape — never reveal whether the account exists
    # (account enumeration).
    ok = {"ok": True}
    if not session.exec(select(User).where(User.email == payload.email)).first():
        return ok

    # 6 cryptographically-random digits; only a salted hash is persisted.
    code = f"{secrets.randbelow(1_000_000):06d}"
    for stale in session.exec(select(PasswordResetCode).where(
            PasswordResetCode.email == payload.email,
            PasswordResetCode.used_at.is_(None))).all():
        session.delete(stale)  # one live code per account
    session.add(PasswordResetCode(
        email=payload.email,
        code_hash=_hash_code(payload.email, code),
        expires_at=(datetime.now(timezone.utc) + timedelta(minutes=RESET_TTL_MIN)).isoformat()))
    session.commit()

    if send_reset_email(payload.email, code):
        return ok

    # Not delivered. Dev logs the code so local testing works; production
    # logs the failure (the stored code stays valid, so a retry succeeds
    # once SMTP is back) but still returns 200 — a 503 here would fire only
    # for existing accounts and leak their existence.
    if settings.is_production:
        log.error("Reset code for %s could not be delivered (SMTP failure); "
                  "it remains valid for %d minutes.", payload.email, RESET_TTL_MIN)
    else:
        log.info("password-reset code for %s: %s (dev SQLite only)", payload.email, code)
    return ok


@router.post("/reset-confirm")
def reset_confirm(payload: ResetConfirm, request: Request, session: Session = Depends(get_session)):
    _check_rate(request, "reset-confirm")
    want = _hash_code(payload.email, payload.code)
    now = datetime.now(timezone.utc)

    live: list[PasswordResetCode] = []
    for row in session.exec(select(PasswordResetCode).where(
            PasswordResetCode.email == payload.email,
            PasswordResetCode.used_at.is_(None))).all():
        if datetime.fromisoformat(row.expires_at) <= now:
            session.delete(row)  # housekeeping: expired codes don't linger
        else:
            live.append(row)

    match = next((r for r in live if r.code_hash == want), None)
    if match is None:
        raise HTTPException(400, "Invalid or expired code")

    user = session.exec(select(User).where(User.email == payload.email)).first()
    if not user:
        raise HTTPException(404, "User not found")

    user.hashed_password = hash_password(payload.new_password)
    session.add(user)
    match.used_at = _now_iso()
    session.add(match)
    for other in live:  # single use: burn every other live code for this account
        if other.id != match.id:
            session.delete(other)
    session.commit()
    return {"ok": True}
