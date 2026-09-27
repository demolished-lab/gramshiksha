from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session
import os

from .config import settings
from .db import create_db_and_tables, engine
from .routers import auth, catalog, dashboards, learn, materials, social
from .seed import seed

app = FastAPI(
    title=settings.app_name,
    description="GramShiksha — Indian school e-learning portal for Class 1-12. "
                "Trilingual (English/हिंदी/मराठी), low-bandwidth & offline friendly.",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(catalog.router)
app.include_router(learn.router)
app.include_router(materials.router)
app.include_router(social.router)
app.include_router(dashboards.router)

# serve uploaded files (dev; in prod use object storage/CDN)
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.on_event("startup")
def on_startup() -> None:
    create_db_and_tables()
    with Session(engine) as session:
        seed(session)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "app": settings.app_name, "version": "0.2.0"}
