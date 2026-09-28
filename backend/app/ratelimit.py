"""Shared in-process rate limiting.

The free-tier target is a single instance, so a dict of timestamps is enough —
no Redis to operate, and the limits stay generous because several siblings may
share one phone and one IP. If you ever scale to multiple workers, back this
with Redis: only `check()` changes.

Usage (two forms):

    @router.post("/things", dependencies=[Depends(rate_limit("things.create"))])
    _rl: None = Depends(rate_limit("materials.upload", 30))
"""
from datetime import datetime, timezone

from fastapi import HTTPException, Request

HITS: dict[tuple[str, str], list[float]] = {}  # (client_ip, endpoint) -> timestamps
DEFAULT_LIMIT = 30  # requests per window
DEFAULT_WINDOW_S = 60.0
_SWEEP_AFTER_KEYS = 512  # keep the dict bounded so long uptime can't leak memory


def check(request: Request, endpoint: str, limit: int = DEFAULT_LIMIT,
          window_s: float = DEFAULT_WINDOW_S) -> None:
    now = datetime.now(timezone.utc).timestamp()
    ip = request.client.host if request.client else "unknown"
    key = (ip, endpoint)

    hits = [t for t in HITS.get(key, []) if now - t < window_s]
    if len(hits) >= limit:
        raise HTTPException(429, "Too many attempts — please wait a minute and retry")
    hits.append(now)
    HITS[key] = hits

    if len(HITS) > _SWEEP_AFTER_KEYS:
        for stale in [k for k, v in HITS.items() if not v or now - max(v) >= window_s]:
            del HITS[stale]


def rate_limit(endpoint: str, limit: int = DEFAULT_LIMIT,
               window_s: float = DEFAULT_WINDOW_S):
    """FastAPI dependency factory: `Depends(rate_limit("name", 30))`."""
    def dep(request: Request) -> None:
        check(request, endpoint, limit, window_s)

    return dep


def clear() -> None:
    """Test hook — resets every bucket."""
    HITS.clear()
