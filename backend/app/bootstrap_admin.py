"""Create or promote the platform administrator of an instance.

Why this exists: production seeds content but never demo accounts
(`SEED_DEMO=auto` is off on Postgres — see README), so a fresh deploy has
*nobody* who can approve teachers, open the admin dashboard or moderate
uploads. Forcing `SEED_DEMO=true` instead would create logins whose passwords
are published in the README, on the public instance.

Render Shell (container code lives in /app/backend):

    cd /app/backend && python -m app.bootstrap_admin admin@school.ac.in 'a-strong-password'

Locally, pointing at the real database:

    DATABASE_URL=postgresql+psycopg://… JWT_SECRET=… \
        .venv/Scripts/python -m app.bootstrap_admin admin@school.ac.in 'a-strong-password'

Idempotent: an existing account with that email is promoted to
platform_admin/active and its password reset. Shell access already implies
full database access, so this trusts nobody new — it only replaces hand-written
SQL with a checked command.
"""
import sys

from sqlmodel import Session, select

from . import db
from .models import User
from .security import hash_password

USAGE = "usage: python -m app.bootstrap_admin <email> <password>"


def bootstrap(session: Session, email: str, password: str) -> tuple[str, int]:
    """Create the admin, or promote+reset whoever already owns that email.

    Returns (action, user_id) where action is "created" | "updated".
    """
    email = email.strip().lower()
    user = session.exec(select(User).where(User.email == email)).first()
    action = "updated" if user else "created"
    if user is None:
        user = User(email=email, name="Administrator")
    user.role = "platform_admin"
    user.role_status = "active"
    # Same minimum as the API's RegisterIn, so a too-short password here
    # would create an account the login form itself would have rejected.
    user.hashed_password = hash_password(password)
    session.add(user)
    session.commit()
    session.refresh(user)
    return action, user.id


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(USAGE)
        return 2
    _, email, password = argv
    if len(password) < 8:
        print("password must be at least 8 characters (the API minimum)")
        return 2
    with Session(db.engine) as session:
        action, user_id = bootstrap(session, email, password)
    print(f"{action} platform admin {email} (id={user_id}, role_status=active)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
