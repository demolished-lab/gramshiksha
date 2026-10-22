from datetime import datetime, timedelta, timezone
from typing import Optional
import hashlib
import logging
import secrets
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import delete as sqlalchemy_delete, func
from sqlmodel import Session, select

from ..config import settings
from ..db import get_session
from ..gamification import seed_badges
from ..mailer import send_reset_email
from ..models import PasswordResetAttempt, PasswordResetCode, User
# NOT dead code: tests clear the limiter and read its config through this
# module (auth_router._RATE / auth_router.RATE_LIMIT) — keep the aliases.
from ..ratelimit import DEFAULT_LIMIT as RATE_LIMIT, DEFAULT_WINDOW_S as RATE_WINDOW_S  # noqa: F401
from ..ratelimit import HITS as _RATE  # noqa: F401
from ..ratelimit import check as _check_rate
from ..ratelimit import rate_limit
from ..security import create_access_token, get_current_user, hash_password, verify_password
from pydantic import BaseModel, EmailStr, Field

log = logging.getLogger("gramshiksha")

router = APIRouter(prefix="/auth", tags=["auth"])

RESET_TTL_MIN = 15  # reset codes live 15 minutes
RESET_CONFIRM_LIMIT = 5


class RegisterIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=72)
    role: str = Field(default="student", max_length=20)
    lang_pref: str = Field(default="hi", max_length=8)
    class_grade: Optional[int] = Field(default=None, ge=1, le=12)
    board: Optional[str] = Field(default=None, max_length=40)
    school_name: str = Field(default="", max_length=120)
    # Invite code ("GS000123") captured from ?ref= by the frontend. Unknown
    # or garbage codes are ignored — registration never fails over them.
    ref: str = Field(default="", max_length=16)


class ProfileUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=80)
    lang_pref: Optional[str] = Field(default=None, max_length=8)
    class_grade: Optional[int] = Field(default=None, ge=1, le=12)
    board: Optional[str] = Field(default=None, max_length=40)
    profile_pic: Optional[str] = Field(default=None, max_length=500)
    # `school_name` is deliberately absent: school membership is set once at
    # registration and must not be self-editable afterwards, or any account
    # could move itself into another school and read/write its scoped data.


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
    # Login always lowercases the address. Store it the same way, or a phone
    # keyboard that capitalises the first letter creates an account nobody can
    # sign back into. Case-insensitive duplicate check also closes the
    # Learner@x.in / learner@x.in double-account hole.
    email = str(payload.email).strip().lower()
    name = payload.name.strip()
    if not name:
        raise HTTPException(422, "Name is required")
    if session.exec(select(User).where(func.lower(User.email) == email)).first():
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
        email=email,
        name=name,
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
    # Return the same session shape as login. The browser can enter the app
    # immediately instead of making a second credential round-trip that can
    # fail on a flaky mobile connection (or because of a keyboard-typed
    # uppercase email that the old login lookup did not match).
    return _login_payload(user)


@router.post("/token")
def login(request: Request, form: OAuth2PasswordRequestForm = Depends(),
          session: Session = Depends(get_session)):
    _check_rate(request, "token")
    email = form.username.strip().lower()
    _check_login_lock(email)
    user = session.exec(select(User).where(func.lower(User.email) == email)).first()
    if not user or not verify_password(form.password, user.hashed_password):
        _record_login_failure(email)
        raise HTTPException(401, "Incorrect email or password")
    _LOGIN_FAILS.pop(email, None)
    return _login_payload(user)


# Per-account brute-force guard, independent of the IP bucket: an attacker who
# rotates X-Forwarded-For (or lands on another instance) still cannot try
# unlimited passwords against one address. In-process, like the IP limiter;
# a restart clears it, which is an acceptable trade for zero infrastructure.
_LOGIN_FAILS: dict[str, list[float]] = {}
_LOGIN_FAIL_LIMIT = 10
_LOGIN_FAIL_WINDOW_S = 15 * 60.0


def _recent_failures(email: str, now: float) -> list[float]:
    return [t for t in _LOGIN_FAILS.get(email, []) if now - t < _LOGIN_FAIL_WINDOW_S]


def _check_login_lock(email: str) -> None:
    now = time.time()
    hits = _recent_failures(email, now)
    if len(hits) >= _LOGIN_FAIL_LIMIT:
        wait = int(_LOGIN_FAIL_WINDOW_S - (now - hits[0])) + 1
        raise HTTPException(
            429, "Too many failed sign-in attempts for this account. Try again later.",
            headers={"Retry-After": str(max(1, wait))})


def _record_login_failure(email: str) -> None:
    now = time.time()
    hits = _recent_failures(email, now)
    hits.append(now)
    _LOGIN_FAILS[email] = hits
    if len(_LOGIN_FAILS) > 5000:  # bound memory under a distributed spray
        for key in [k for k, v in _LOGIN_FAILS.items()
                    if not v or now - max(v) >= _LOGIN_FAIL_WINDOW_S]:
            del _LOGIN_FAILS[key]


def _login_payload(user: User) -> dict:
    token = create_access_token(user.email, user.role)
    # role_status rides on the login response so the UI can render the
    # pending/suspended notice immediately, without a second /auth/me round
    # trip that would first show the privileged page and then its 403.
    return {"access_token": token, "token_type": "bearer",
            "id": user.id, "email": user.email,
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
    email = form.username.strip().lower()
    user = session.exec(select(User).where(func.lower(User.email) == email)).first()
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
              session: Session = Depends(get_session),
              _rl: None = Depends(rate_limit("auth.me.update", 30))):
    data = payload.model_dump(exclude_unset=True)
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
    email = str(payload.email).strip().lower()
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
    if not session.exec(select(User).where(func.lower(User.email) == email)).first():
        return ok

    # 6 cryptographically-random digits; only a salted hash is persisted.
    code = f"{secrets.randbelow(1_000_000):06d}"
    for stale in session.exec(select(PasswordResetCode).where(
            PasswordResetCode.email == email,
            PasswordResetCode.used_at.is_(None))).all():
        session.delete(stale)  # one live code per account
    session.add(PasswordResetCode(
        email=email,
        code_hash=_hash_code(email, code),
        expires_at=(datetime.now(timezone.utc) + timedelta(minutes=RESET_TTL_MIN)).isoformat()))
    session.commit()

    if send_reset_email(email, code):
        return ok

    # Not delivered. Dev logs the code so local testing works; production
    # logs the failure (the stored code stays valid, so a retry succeeds
    # once SMTP is back) but still returns 200 — a 503 here would fire only
    # for existing accounts and leak their existence.
    if settings.is_production:
        log.error("Reset code for %s could not be delivered (SMTP failure); "
                  "it remains valid for %d minutes.", email, RESET_TTL_MIN)
    else:
        log.info("password-reset code for %s: %s (dev SQLite only)", email, code)
    return ok


@router.post("/reset-confirm")
def reset_confirm(payload: ResetConfirm, request: Request, session: Session = Depends(get_session)):
    _check_rate(request, "reset-confirm")
    now = datetime.now(timezone.utc)
    email = str(payload.email).strip().lower()
    window_start = now - timedelta(minutes=RESET_TTL_MIN)
    # Retain only the rolling window. The row log makes lockout shared across
    # workers and client IPs rather than another process-local limiter.
    session.exec(sqlalchemy_delete(PasswordResetAttempt).where(
        PasswordResetAttempt.created_at < window_start))
    recent = session.exec(select(PasswordResetAttempt).where(
        PasswordResetAttempt.email == email,
        PasswordResetAttempt.created_at >= window_start)).all()
    if len(recent) >= RESET_CONFIRM_LIMIT:
        session.commit()
        raise HTTPException(429, "Too many reset-code guesses. Request a new code after 15 minutes.")
    session.add(PasswordResetAttempt(email=email, created_at=now))
    session.commit()

    want = _hash_code(email, payload.code)

    live: list[PasswordResetCode] = []
    for row in session.exec(select(PasswordResetCode).where(
            PasswordResetCode.email == email,
            PasswordResetCode.used_at.is_(None))).all():
        if datetime.fromisoformat(row.expires_at) <= now:
            session.delete(row)  # housekeeping: expired codes don't linger
        else:
            live.append(row)

    match = next((r for r in live if r.code_hash == want), None)
    if match is None:
        session.commit()
        raise HTTPException(400, "Invalid or expired code")

    user = session.exec(select(User).where(func.lower(User.email) == email)).first()
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
