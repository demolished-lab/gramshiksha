FROM python:3.12-slim

# Unbuffered stdout so Render's log view shows request lines as they happen
# (a buffered container logs nothing until the process flush/exit), no .pyc
# writes (the app dir is read-only for the runtime user below).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY backend ./backend

# Run as an unprivileged user: this process faces the public internet, so a
# remote-code-execution bug must not land on a root shell inside the
# container. The uploads dir is created and chowned before dropping root —
# Cloudinary is the production store, but the local fallback must still be
# writable.
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /app/backend/uploads \
    && chown -R app:app /app
USER app

ENV PORT=8000
CMD ["sh", "-c", "uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]
