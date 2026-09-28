import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from sqlmodel import Session, text
import os

from .config import settings
from .db import create_db_and_tables, engine
from .routers import auth, catalog, dashboards, learn, materials, progress, social
from .routers import lessons
from .seed import seed

log = logging.getLogger("gramshiksha")


def _configure_logging() -> None:
    """App logging must not depend on how the host process set up the root logger.

    Three ways it silently failed before: uvicorn attaches handlers only to its
    *own* loggers; `logging.basicConfig()` is a no-op once root already has a
    handler; and a library calling `fileConfig()` — alembic's ini does exactly
    that, at every boot — demotes root to WARNING. Whichever happened, every
    INFO line the app wrote (request lines, the dev password-reset code the
    README documents) vanished while uvicorn's own lines happily survived.

    So the app logger carries its own handler: predictable under uvicorn,
    gunicorn, `python -m` and pytest alike. Sentry is initialised with the
    FastAPI integration only (no LoggingIntegration), so log records never
    reached it anyway — captured exceptions are unaffected by propagate=False.
    """
    handler = logging.StreamHandler()  # stderr, same stream as uvicorn
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    if not log.handlers:
        log.addHandler(handler)
    log.setLevel(logging.INFO)
    log.propagate = False

    # One sane handler for everything else that logs through root (third-party
    # libraries, alembic when run standalone)…
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    # …but not SQL: with root at INFO, every SELECT would be echoed.
    for name in ("sqlalchemy.engine", "sqlalchemy.engine.Engine", "sqlalchemy.pool"):
        logging.getLogger(name).setLevel(logging.WARNING)


_configure_logging()

# Health checks are polled constantly by Render — logging them would bury
# everything else.
_QUIET_PATHS = {"/health", "/ready", "/api/health", "/api/ready"}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        resp = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resp.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        return resp


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Stamps every request with an id, echoes it as `X-Request-ID`, times it
    and writes one log line — so "student says it errored" turns into an exact
    log/Sentry lookup instead of guesswork. The id lives in `scope["state"]`,
    so the 500 handler below (which runs *outside* this middleware) can still
    return it to the client."""

    async def dispatch(self, request, call_next):
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        request.state.request_id = rid
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            log.error("Unhandled error in %s %s (request_id=%s)",
                      request.method, request.url.path, rid, exc_info=True)
            raise
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        response.headers.setdefault("X-Request-ID", rid)
        if request.url.path not in _QUIET_PATHS:
            log.log(logging.ERROR if response.status_code >= 500 else logging.INFO,
                    "%s %s -> %s %dms (request_id=%s)",
                    request.method, request.url.path, response.status_code,
                    elapsed_ms, rid)
        return response


def docs_paths(s=None) -> tuple[str | None, str | None]:
    """(docs_url, openapi_url) — the interactive API reference is a map of the
    attack surface, so it's off in production unless ENABLE_DOCS=true."""
    s = s or settings
    return ("/docs", "/openapi.json") if s.docs_on else (None, None)


def check_production_safety() -> None:
    """Refuse to boot a configuration that would lose data or hand out a known
    signing key. Raising here makes uvicorn exit non-zero, so the deploy fails
    loudly (Render shows this message) instead of silently running unsafe."""
    if not settings.is_production:
        if settings.jwt_secret == "dev-secret-change-me":
            log.warning("JWT_SECRET is the dev default — set a random 64-char secret in production.")
        return

    problems: list[str] = []
    if settings.jwt_secret == "dev-secret-change-me":
        problems.append(
            "JWT_SECRET is still the dev default 'dev-secret-change-me' — anyone who has read "
            "the README can forge a platform_admin token. Set a random 64-char value "
            "(Render: JWT_SECRET with generateValue: true).")
    if not settings.cloudinary_enabled and not settings.allow_ephemeral_uploads:
        problems.append(
            "Uploads would be written to an ephemeral disk and destroyed on every redeploy, "
            "leaving broken download rows in the DB. Set CLOUDINARY_CLOUD_NAME / "
            "CLOUDINARY_API_KEY / CLOUDINARY_API_SECRET — or mount a persistent disk at "
            "backend/uploads and set ALLOW_EPHEMERAL_UPLOADS=true.")
    if problems:
        raise RuntimeError("Refusing to start in production:\n - " + "\n - ".join(problems))

    if not settings.smtp_enabled:
        log.warning("SMTP not configured — /auth/reset-request will answer 503 until SMTP_HOST is set.")
    if settings.seed_demo_enabled:
        log.warning("SEED_DEMO=true in production — demo accounts with published passwords "
                    "will be created. Set SEED_DEMO=false unless this is a throwaway instance.")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.sentry_dsn:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.fastapi import FastApiIntegration
            sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.sentry_env,
                            send_default_pii=False, traces_sample_rate=0.05)
            log.info("Sentry error tracking enabled (env=%s).", settings.sentry_env)
        except Exception as exc:  # noqa: BLE001 — tracking must never break boot
            log.warning("Sentry init failed: %s", exc)
    check_production_safety()
    create_db_and_tables()
    with Session(engine) as session:
        seed(session)
    yield


_docs_url, _openapi_url = docs_paths()

app = FastAPI(
    title=settings.app_name,
    description="GramShiksha — Indian school e-learning portal for Class 1-12. "
                "Trilingual (English/हिंदी/मराठी), low-bandwidth & offline friendly.",
    version="0.2.0",
    lifespan=lifespan,
    docs_url=_docs_url,       # None in production (see ENABLE_DOCS)
    openapi_url=_openapi_url, # None in production
    redoc_url=None,
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """One JSON shape for unexpected failures, carrying the request id the
    client can quote back to us. The traceback goes to the log line emitted by
    RequestContextMiddleware (and Sentry, if configured) — never into the
    response body."""
    rid = getattr(request.state, "request_id", "-")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": rid},
        headers={"X-Request-ID": rid},
    )


app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Added last ⇒ outermost: ids/timing cover CORS preflights and header
# middleware too, and its request id survives into the 500 handler above.
app.add_middleware(RequestContextMiddleware)

# Dev / backward-compatible routes (no prefix — matches vite proxy + tests)
app.include_router(auth.router)
app.include_router(catalog.router)
app.include_router(learn.router)
app.include_router(materials.router)
app.include_router(social.router)
app.include_router(dashboards.router)
# Authored separately from learn.py/dashboards.py; both were long written
# against the current models but never mounted (see each module's docstring).
app.include_router(lessons.router)
app.include_router(progress.router)

# Production routes under /api (matches Netlify/Vercel rewrites /api/* -> backend /api/*)
app.include_router(auth.router, prefix="/api")
app.include_router(catalog.router, prefix="/api")
app.include_router(learn.router, prefix="/api")
app.include_router(materials.router, prefix="/api")
app.include_router(social.router, prefix="/api")
app.include_router(dashboards.router, prefix="/api")
app.include_router(lessons.router, prefix="/api")
app.include_router(progress.router, prefix="/api")

# Uploaded files are served ONLY via the authenticated
# GET /materials/{id}/download endpoint (approval + visibility checked).
# Never mount the upload dir publicly — pending/private files must not be
# reachable by guessing /uploads/<name>.
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "app": settings.app_name, "version": "0.2.0"}


@app.get("/api/health")
def health_api() -> dict:
    return {"status": "ok", "app": settings.app_name, "version": "0.2.0"}


@app.get("/ready")
def ready() -> dict:
    """Readiness: app + DB reachable (use as Render healthCheckPath: /ready)."""
    try:
        with Session(engine) as session:
            session.exec(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as exc:  # noqa: BLE001 — readiness must report, not crash
        log.warning("readiness DB check failed: %s", exc)
        return {"status": "degraded", "reason": "db_unreachable"}


@app.get("/api/ready")
def ready_api() -> dict:
    return ready()
