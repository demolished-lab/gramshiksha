"""Smart Book Finder: find any book as fast as honestly possible.

Three tiers, cheapest first:

1. **Library search** — every class/board, one indexed query: milliseconds.
2. **Live official scan** — eBalbharati for the requested class, reusing the
   crawler's proven ASP.NET postback (same code path as `crawl_ebalbharati.py`),
   fuzzy title match, PDF HEAD-verified, then the Textbook row is created on
   the spot — "found" means the Download button works immediately.
3. **Request queue** — nothing official to be found → a BookRequest; keep-warm
   posts /library/scan-requests every 10 minutes, so "cataloged but not here"
   resolves itself with zero manual work, and the requester is notified.

Timing is displayed honestly: responses carry `eta_seconds` (the estimate a
scan of that scope takes) and `elapsed_s` (what it actually took). Only
government portals are ever scanned — never pirated mirrors.
"""
import json
import re
import sys
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..config import settings
from ..db import get_session
from ..models import BookRequest, Notification, Textbook, User, utcnow
from ..ratelimit import rate_limit
from ..security import get_current_user
from .catalog import _textbook_out, check_url

# scripts/ is a sibling of app/ — put the backend root on sys.path so the
# import works no matter what cwd the server was started from.
_BACKEND_ROOT = str(Path(__file__).resolve().parents[2])
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)
from scripts.crawl_ebalbharati import (  # noqa: E402
    MEDIUM_LANG, MEDIUM_WORDS, UA, WS_RE, crawl, guess_subject, parse_part,
    subject_fallback,
)

router = APIRouter(tags=["library"])

SCAN_YEAR = "2026"        # eBalbharati catalog year (matches the crawler default)
SCAN_FTYPE = "101"        # 101 = Text Books filter
SCAN_BUDGET_S = 45.0      # hard deadline for one live scan
SCAN_COOLDOWN_S = 120.0   # min gap between scan-requests passes
MAX_SCAN_REQUESTS = 10    # pendings considered per pass
PORTAL = "https://books.ebalbharati.in"
PDF_BASE = "https://ebooks.ebalbharati.in/pdfs"
COVER_BASE = "https://books.ebalbharati.in/BookCovers"

_last_scan_at = [0.0]  # module clock — reset by tests

_optional_oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)

_DEV_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
_STOPWORDS = {w.lower() for w in MEDIUM_WORDS} | {
    "class", "std", "book", "कक्षा", "वी", "वीं", "इ", "ठी", "पुस्तक"}


def _norm(s: str) -> str:
    """Search-normalized text: Devanagari digits → ASCII, lower, collapsed ws."""
    return re.sub(r"\s+", " ", (s or "").translate(_DEV_DIGITS).lower()).strip()


def _tokens(s: str) -> set[str]:
    return {tok for tok in s.split() if tok not in _STOPWORDS}


def fuzzy_match(query: str, title: str) -> bool:
    """Does this candidate title plausibly IS the searched book?

    Substring either way, or ≥60% of the shorter side's content tokens shared
    — loose enough for "गणित 8" vs "८ वी गणित" (digit-normalised, medium words
    dropped), tight enough not to swallow the whole class. Digit-only queries
    ("8") match nothing but containment: a number is not a book.
    """
    a, b = _norm(query), _norm(title)
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    at, bt = _tokens(a), _tokens(b)
    if not at or not bt or all(tok.isdigit() for tok in at):
        return False
    return len(at & bt) / min(len(at), len(bt)) >= 0.6


def search_library(session: Session, q: str, limit: int = 8) -> list[Textbook]:
    """Tier 1: instant across every class/board, deep-linked books first."""
    pattern = f"%{q}%"
    rows = session.exec(
        select(Textbook).where(
            Textbook.title.ilike(pattern)
            | Textbook.subject_name.ilike(pattern)
        ).order_by(Textbook.clicks.desc()).limit(limit)).all()
    return sorted(rows, key=lambda r: 0 if (r.deep_url and r.last_ok) else 1)


def scan_official(q: str, grade: int, pref_langs: list[str],
                  deadline: float) -> tuple[list[dict], list[str]]:
    """Tier 2: crawl eBalbharati for this class, preferred mediums first.

    Returns (verified candidates, mediums actually scanned). Stops at the
    deadline — the caller turns an exhausted budget into an honest queue
    position rather than an optimistic lie. delay=0.4s keeps the postbacks
    polite; max_pages=2 caps a runaway pagination loop.
    """
    import httpx

    codes = {lang: code for code, lang in MEDIUM_LANG.items()}
    order = [codes[lc] for lc in pref_langs if lc in codes]
    order += [code for code in codes.values() if code not in order]
    class_code = str(200 + grade)  # 201..212 == 1st..12th (portal contract)
    scanned: list[str] = []
    out: list[dict] = []
    with httpx.Client(headers=UA, follow_redirects=True) as client:
        for code in order:
            if time.monotonic() >= deadline:
                break
            try:
                hits = crawl(client, SCAN_YEAR, SCAN_FTYPE, class_code, code,
                             delay=0.4, max_pages=2)
            except Exception:
                continue  # one flaky postback must not fail the whole locate
            lang = MEDIUM_LANG.get(code, "")
            scanned.append(lang)
            for bid, title in (h for h in hits if fuzzy_match(q, h[1])):
                pdf = f"{PDF_BASE}/{bid}.pdf"
                if not check_url(pdf):
                    continue  # verified-live rule: dead PDFs never ship
                out.append({"book_id": bid, "title": title, "pdf": pdf,
                            "cover": f"{COVER_BASE}/{bid}.jpg", "lang": lang})
                return out, scanned
    return out, scanned


def ingest_hit(session: Session, *, title: str, pdf: str, cover: str,
               grade: int, lang: str) -> Optional[Textbook]:
    """Create — or return — the Textbook row for a verified official hit.

    Same rules as the crawler's apply: the PDF id is the idempotency anchor,
    the subject comes from the keyword guess with a cleaned-title fallback,
    parts keep their label. Board is always Maharashtra: eBalbharati is the
    Maharashtra publisher whatever board the seeker studies.
    """
    existing = session.exec(
        select(Textbook).where(Textbook.deep_url == pdf)).first()
    if existing is not None:
        return existing
    subject = guess_subject(title, lang) or subject_fallback(title)
    if not subject:
        return None
    row = Textbook(
        board="Maharashtra HSC" if grade >= 11 else "Maharashtra SSC",
        class_grade=grade, subject_name=subject, lang=lang,
        part_label=parse_part(title), title=WS_RE.sub(" ", title).strip(),
        source_url=PORTAL,
        publisher="Official", deep_url=pdf, cover_url=cover,
        last_ok=True, last_checked=None)
    session.add(row)
    session.flush()  # id must exist for the response / request link
    return row


def _queue(session: Session, *, q: str, grade: Optional[int], board: str,
           lang: str, user_id: Optional[int]) -> tuple[BookRequest, int]:
    """Record the ask (deduped on query+grade) and return its queue position."""
    conds = [BookRequest.query == q, BookRequest.status == "pending"]
    if grade is None:
        conds.append(BookRequest.class_grade.is_(None))
    else:
        conds.append(BookRequest.class_grade == grade)
    row = session.exec(
        select(BookRequest).where(*conds).order_by(BookRequest.created_at)).first()
    if row is None:
        row = BookRequest(user_id=user_id, query=q, class_grade=grade,
                          board=board, lang=lang)
        session.add(row)
        session.flush()
    if user_id and row.user_id is None:
        row.user_id = user_id  # a signed-in retry claims an anonymous ask
        session.add(row)
    waiting = session.exec(select(BookRequest).where(
        BookRequest.query == q, BookRequest.status == "pending")).all()
    return row, len(waiting)


def _optional_user(token: Optional[str] = Depends(_optional_oauth2),
                   session: Session = Depends(get_session)) -> Optional[User]:
    """locate() works signed-in (queue → notification) or anonymous (queue →
    check back); even a *stale* token must not 401 somebody's search."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.jwt_secret,
                             algorithms=[settings.jwt_algorithm])
        email = payload.get("sub")
    except JWTError:
        return None
    if not email:
        return None
    return session.exec(select(User).where(User.email == email)).first()


class LocateIn(BaseModel):
    q: str = Field(min_length=1, max_length=120)
    class_grade: Optional[int] = Field(default=None, ge=1, le=12)
    board: str = ""
    lang: str = ""


def _eta_seconds(lang: str) -> int:
    """Estimate the UI shows *before* firing: one medium ≈ 10 s,
    a multi-medium sweep ≈ 30 s (measured against the live portal)."""
    return 10 if lang else 30


@router.post("/library/locate",
             dependencies=[Depends(rate_limit("library.locate", 6, 60.0))])
def locate(payload: LocateIn, session: Session = Depends(get_session),
           user: Optional[User] = Depends(_optional_user)) -> dict:
    """Find a book: library first (ms), then the official portal (seconds),
    then the request queue — with honest elapsed/ETA either way."""
    t0 = time.monotonic()
    q = _norm(payload.q)
    if not q:
        raise HTTPException(422, "Empty search — type a book title")

    books = search_library(session, q)
    if books:
        return {"result": "found", "source": "library",
                "books": [_textbook_out(b) for b in books],
                "eta_seconds": 0, "elapsed_s": round(time.monotonic() - t0, 1)}

    scanned: list[str] = []
    if payload.class_grade:
        pref = [payload.lang] if payload.lang else ["mr", "hi", "en"]
        hits, scanned = scan_official(q, payload.class_grade, pref,
                                      t0 + SCAN_BUDGET_S)
        if hits:
            h = hits[0]
            row = ingest_hit(session, title=h["title"], pdf=h["pdf"],
                             cover=h["cover"], grade=payload.class_grade,
                             lang=h["lang"] or payload.lang or "mr")
            if row is not None:
                session.commit()
                return {"result": "found", "source": "official",
                        "books": [_textbook_out(row)], "scanned_langs": scanned,
                        "eta_seconds": _eta_seconds(payload.lang),
                        "elapsed_s": round(time.monotonic() - t0, 1)}

    _req, position = _queue(session, q=q, grade=payload.class_grade,
                            board=payload.board, lang=payload.lang,
                            user_id=user.id if user else None)
    session.commit()
    return {"result": "queued", "position": position, "pending": True,
            "scanned_langs": scanned, "eta_seconds": _eta_seconds(payload.lang),
            "elapsed_s": round(time.monotonic() - t0, 1)}


@router.post("/library/scan-requests",
             dependencies=[Depends(rate_limit("library.scan", 4, 60.0))])
def scan_requests(session: Session = Depends(get_session)) -> dict:
    """Keep-warm re-scan of pending asks (every 10 min in production).

    Tier order per request: library first (a later locate/apply may already
    have ingested it), then the official portal. A module-level cooldown
    keeps this public endpoint from turning into a crawl cannon.
    """
    now = time.monotonic()
    if now - _last_scan_at[0] < SCAN_COOLDOWN_S:
        return {"skipped": True,
                "cooldown_s": round(SCAN_COOLDOWN_S - (now - _last_scan_at[0]))}
    _last_scan_at[0] = now

    pendings = session.exec(
        select(BookRequest).where(BookRequest.status == "pending")
        .order_by(BookRequest.created_at).limit(MAX_SCAN_REQUESTS)).all()
    found = 0
    deadline = time.monotonic() + SCAN_BUDGET_S
    for req in pendings:
        if time.monotonic() >= deadline:
            break
        row = None
        books = search_library(session, req.query, limit=1)
        if books:
            row = books[0]
        elif req.class_grade:
            pref = [req.lang] if req.lang else ["mr", "hi", "en"]
            hits, _ = scan_official(req.query, req.class_grade, pref, deadline)
            if hits:
                row = ingest_hit(session, title=hits[0]["title"],
                                 pdf=hits[0]["pdf"], cover=hits[0]["cover"],
                                 grade=req.class_grade,
                                 lang=hits[0]["lang"] or req.lang or "mr")
        if row is not None:
            req.status = "found"
            req.textbook_id = row.id
            req.found_at = utcnow()
            session.add(req)
            if req.user_id:
                session.add(Notification(
                    user_id=req.user_id, type="book_available",
                    payload=json.dumps({"request_id": req.id,
                                        "textbook_id": row.id,
                                        "title": row.title})))
            found += 1
    session.commit()
    remaining = session.exec(select(BookRequest).where(
        BookRequest.status == "pending")).all()
    return {"scanned": len(pendings), "found": found,
            "pending": len(remaining)}


@router.get("/library/requests")
def my_requests(user: User = Depends(get_current_user),
                session: Session = Depends(get_session)) -> list[dict]:
    """The signed-in learner's asks and their state — the persistent "you're
    #N in line / it arrived" view behind the search panel."""
    rows = session.exec(
        select(BookRequest).where(BookRequest.user_id == user.id)
        .order_by(BookRequest.created_at.desc()).limit(20)).all()
    return [
        {"id": r.id, "query": r.query, "class_grade": r.class_grade,
         "status": r.status, "textbook_id": r.textbook_id,
         "created_at": r.created_at.isoformat(),
         "found_at": r.found_at.isoformat() if r.found_at else None}
        for r in rows
    ]
