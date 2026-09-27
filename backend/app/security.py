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


def require_roles(*roles: str):
    """Route dependency: allow only listed roles (admins inherit teacher powers)."""
    allowed = set(roles)

    def dep(user: User = Depends(get_current_user)) -> User:
        effective = set(roles)
        if user.role == "platform_admin":
            effective |= {"teacher", "school_admin"}
        if user.role == "school_admin" and "teacher" in allowed:
            effective |= {"teacher"}
        if user.role not in effective:
            raise HTTPException(status_code=403, detail=f"Requires role: {', '.join(sorted(allowed))}")
        return user

    return dep


# Convenience deps
require_teacher = require_roles("teacher")
require_student = require_roles("student")
require_admin = require_roles("school_admin", "platform_admin")
require_any = require_roles("student", "teacher", "parent", "school_admin", "platform_admin")
