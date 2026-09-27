from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

from .config import settings

connect_args = {}
engine_kwargs: dict = {}

if settings.database_url.startswith("sqlite"):
    # FastAPI threadpool + SQLite: share one connection across threads.
    engine_kwargs["connect_args"] = {"check_same_thread": False}
    engine_kwargs["poolclass"] = StaticPool
else:
    # Neon/Postgres in production.
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_size"] = 5
    engine_kwargs["max_overflow"] = 5

engine = create_engine(settings.database_url, **engine_kwargs)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
