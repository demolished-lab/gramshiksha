from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select

from .config import settings
from .db import get_session
from .models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def hash_password(password: str) -> str:
    return pwd_context.hash(password[:72])


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain[:72], hashed)


def create_access_token(subject: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "role": role, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> User:
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        email: str | None = payload.get("sub")
        if email is None:
            raise cred_exc
    except JWTError:
        raise cred_exc
    user = session.exec(select(User).where(User.email == email)).first()
    if user is None:
        raise cred_exc
    return user


_optional_oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)


def optional_user(
    token: str | None = Depends(_optional_oauth2),
    session: Session = Depends(get_session),
) -> User | None:
    """Like get_current_user, but anonymous callers get None instead of 401.

    For free content endpoints (practice questions, public material list) so
    a logged-out visitor sees the library instead of an error page. Anything
    that records progress or serves gated files keeps get_current_user.
    """
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        email: str | None = payload.get("sub")
    except JWTError:
        return None
    if email is None:
        return None
    return session.exec(select(User).where(User.email == email)).first()


def has_role(user: User, *roles: str) -> bool:
    """True when `user` holds one of `roles` *and* the account is approved.

    The inline role checks in routers (moderator-only deletes, doubt
    resolution, draft previews) must go through this rather than comparing
    `user.role` directly — otherwise a self-registered teacher awaiting
    approval keeps every privilege route dependencies take away.
    """
    return user.role in roles and user.role_status == "active"


def _status_detail(role_status: str) -> str:
    """Why an account that *passed* the role test is still refused.

    The message must match what actually happened: a fresh teacher signup
    ("pending") and a withdrawn approval ("suspended") need different
    operator responses, and one blanket message hides which one it is.
    """
    return {
        "pending": "Account pending approval",
        "suspended": "Account suspended",
    }.get(role_status, f"Account status: {role_status}")


def require_roles(*roles: str):
    """Route dependency: allow only listed roles (admins inherit teacher powers).

    A pending account passes the role test but then fails here: registration
    hands out the `teacher` role to anyone, so approval is what actually
    confers privilege. The distinct message tells a fresh signup why it is
    blocked instead of leaving them with "Requires role: teacher", which would
    be untrue.

    Inheritance is one-way and only into *teacher* gates: the role test must
    compare against the caller's own role, so an admin was previously refused
    by every `require_teacher` route (the teacher dashboard happily rendered
    its forms while the API answered 403). Student/parent-only gates stay shut
    for admins — they inherit teaching powers, not a learner's seat.
    """
    allowed = set(roles)

    def dep(user: User = Depends(get_current_user)) -> User:
        effective = set(roles)
        if "teacher" in allowed and user.role in ("platform_admin", "school_admin"):
            effective |= {user.role}
        if user.role not in effective:
            raise HTTPException(status_code=403, detail=f"Requires role: {', '.join(sorted(allowed))}")
        if user.role_status != "active":
            raise HTTPException(status_code=403, detail=_status_detail(user.role_status))
        return user

    return dep


# Convenience deps
require_teacher = require_roles("teacher")
require_student = require_roles("student")
require_admin = require_roles("school_admin", "platform_admin")


def require_any(user: User = Depends(get_current_user)) -> User:
    """Any signed-in account.

    Deliberately *not* approval-gated: material uploads go through this, and a
    teacher still awaiting approval must be able to contribute — their upload
    simply starts as `pending` like a student's (see routers.materials),
    instead of auto-publishing the way an approved teacher's does.
    """
    if user.role not in ("student", "teacher", "parent", "school_admin", "platform_admin"):
        raise HTTPException(status_code=403,
                            detail="Requires a student, teacher, parent or admin account")
    return user
