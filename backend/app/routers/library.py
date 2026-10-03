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
from ..models import BookRequest, Notification, ReadingPick, Textbook, User, utcnow
from ..ratelimit import rate_limit
from ..security import get_current_user, require_teacher
from .catalog import _check_stream, _textbook_out, check_url
from ..streams import stream_for

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
        stream=stream_for(grade, subject),
        part_label=parse_part(title), title=WS_RE.sub(" ", title).strip(),
        source_url=PORTAL,
        publisher="Official", deep_url=pdf, cover_url=cover,
        last_ok=True, last_checked=None)
    session.add(row)
    session.flush()  # id must exist for the response / request link
    return row


def _queue(session: Session, *, q: str, grade: Optional[int], board: str,
           lang: str, user_id: Optional[int],
           stream: str = "") -> tuple[BookRequest, int]:
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
                          board=board, lang=lang, stream=stream)
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
    stream: str = ""


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
                            stream=_check_stream(payload.stream),
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
         "status": r.status, "textbook_id": r.textbook_id, "stream": r.stream,
         "created_at": r.created_at.isoformat(),
         "found_at": r.found_at.isoformat() if r.found_at else None}
        for r in rows
    ]


# ---------- Monthly Reading List (book club) ------------------------------
# "Rich Dad Poor Dad" and friends: a teacher posts one pick a month, every
# student sees it — book club, not homework. Each pick links to the catalog
# when it can ("Read now" opens the in-app reader) and to the Smart Book
# Finder when it cannot, so an un-cataloged pick queues itself instead of
# becoming a dead end.

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_READING_WINDOW = 3  # months returned: this one and the two before it


class ReadingIn(BaseModel):
    month: str = Field(min_length=7, max_length=7)   # "2026-10"
    title: str = Field(min_length=2, max_length=160)
    author: str = Field(default="", max_length=80)
    note: str = Field(default="", max_length=600)
    lang: str = Field(default="", max_length=8)
    subject_name: str = Field(default="", max_length=80)
    class_grade: Optional[int] = Field(default=None, ge=1, le=12)
    board: str = Field(default="", max_length=40)
    stream: str = Field(default="", max_length=12)
    textbook_id: Optional[int] = Field(default=None, ge=1)


def _recent_months(count: int = _READING_WINDOW) -> list[str]:
    """[this month, previous, …] as ISO strings — the window keeps a stale
    pick from sitting at the top of the public list forever.

    One month of *lead* too (+1 … −(count−1)): the server runs UTC while the
    audience is IST (UTC+5:30), so a pick posted between 00:00 and 05:30 on
    the 1st — or pre-posted for next month — would otherwise be invisible for
    hours even though the teacher just published it.
    """
    now = utcnow()
    out = []
    for delta in range(1, -count, -1):  # count+1 months: +1, 0, −1, …, −(count−1)
        year, month = now.year, now.month + delta
        while month <= 0:
            month, year = month + 12, year - 1
        while month > 12:
            month, year = month - 12, year + 1
        out.append(f"{year:04d}-{month:02d}")
    return out


def _pick_out(p: ReadingPick, teacher_name: str, readable: bool) -> dict:
    return {
        "id": p.id, "month": p.month, "title": p.title, "author": p.author,
        "note": p.note, "lang": p.lang, "subject_name": p.subject_name,
        "class_grade": p.class_grade, "board": p.board, "stream": p.stream,
        "textbook_id": p.textbook_id, "readable": readable,
        "teacher_name": teacher_name, "created_at": p.created_at.isoformat(),
    }


@router.get("/library/reading")
def reading_list(mine: bool = False,
                 stream: str = "",
                 user: Optional[User] = Depends(_optional_user),
                 session: Session = Depends(get_session)) -> list[dict]:
    """This month's reading list — public by decision (any student, any class).

    Newest first, and readable means the pick already has a healthy deep PDF
    in the catalog (so the UI can offer "Read now" honestly). Teachers and
    books are prefetched in one query each: per-row round-trips to Neon cost
    ~0.4 s, which would turn this into a slow public page.

    `mine=1` narrows the answer to the signed-in teacher's own picks — that
    is the management view behind the dashboard's withdraw button, and it
    needs no teacher_id in the public payload.
    """
    rows = session.exec(
        select(ReadingPick).where(ReadingPick.month.in_(_recent_months()))
        .order_by(ReadingPick.month.desc(), ReadingPick.id.desc())
        .limit(60)).all()
    if _check_stream(stream):
        # Common picks ("") belong to every stream's shelf.
        rows = [r for r in rows if r.stream in ("", stream)]
    if mine:
        if user is None:
            raise HTTPException(401, "Sign in to see your own reading picks")
        rows = [r for r in rows if r.teacher_id == user.id]
    if not rows:
        return []
    teacher_ids = {r.teacher_id for r in rows}
    book_ids = {r.textbook_id for r in rows if r.textbook_id}
    teachers = {u.id: (u.name or u.email.split("@")[0]) for u in session.exec(
        select(User).where(User.id.in_(teacher_ids))).all()}
    books = {b.id: b for b in session.exec(
        select(Textbook).where(Textbook.id.in_(book_ids))).all()} if book_ids else {}
    return [
        _pick_out(r, teachers.get(r.teacher_id, ""),
                  bool(r.textbook_id and books.get(r.textbook_id)
                       and books[r.textbook_id].deep_url
                       and books[r.textbook_id].last_ok))
        for r in rows
    ]


@router.post("/library/reading",
             dependencies=[Depends(rate_limit("library.reading", 12, 60.0))])
def create_reading(payload: ReadingIn,
                   teacher: User = Depends(require_teacher),
                   session: Session = Depends(get_session)) -> dict:
    """Post (or update) this month's pick.

    Only an approved teacher may post; re-posting the same title in the same
    month rewrites the note instead of stacking duplicates; and the pick is
    linked to the catalog automatically when the title already resolves there
    — otherwise the student gets "Find this book", which queues it for the
    finder. An unknown textbook_id is refused rather than accepted as a dead
    "Read now".
    """
    if not _MONTH_RE.match(payload.month):
        raise HTTPException(422, "month must be YYYY-MM")
    book = None
    if payload.textbook_id:
        book = session.get(Textbook, payload.textbook_id)
        if book is None:
            raise HTTPException(422, "textbook_id does not exist")
    title = WS_RE.sub(" ", payload.title).strip()

    same_month = session.exec(select(ReadingPick).where(
        ReadingPick.teacher_id == teacher.id,
        ReadingPick.month == payload.month)).all()
    row = next((r for r in same_month if _norm(r.title) == _norm(title)), None)

    if book is None:
        # Link it only if this really is that book — a fuzzy near-miss would
        # hand every student the wrong "Read now".
        hit = search_library(session, _norm(title), limit=1)
        if hit and fuzzy_match(title, hit[0].title):
            book = hit[0]

    created = row is None
    if row is None:
        row = ReadingPick(teacher_id=teacher.id, month=payload.month, title=title)
    row.author = payload.author
    row.note = payload.note
    row.lang = payload.lang
    row.subject_name = payload.subject_name
    row.class_grade = payload.class_grade
    row.board = payload.board
    # Explicit stream wins; otherwise derive it from grade+subject, or inherit
    # the linked book's — a pick never claims a stream it doesn't belong to.
    derived = (_check_stream(payload.stream) or stream_for(
        payload.class_grade, payload.subject_name)
        or (book.stream if book is not None else ""))
    row.stream = derived
    if book is not None:
        row.textbook_id = book.id
    # else: a new pick has no link (the student gets "Find this book"), and an
    # edited one keeps the link it already had — the row was matched on the
    # title, so it is still that same book.
    session.add(row)
    session.commit()
    session.refresh(row)
    return _pick_out(row, teacher.name or teacher.email.split("@")[0],
                     bool(book and book.deep_url and book.last_ok)) | {"created": created}


@router.delete("/library/reading/{pick_id}")
def delete_reading(pick_id: int, user: User = Depends(get_current_user),
                   session: Session = Depends(get_session)) -> dict:
    """A teacher withdraws their own pick; admins can withdraw any (an
    inappropriate or mistaken pick has to be removable by the platform, not
    only by whoever posted it)."""
    row = session.get(ReadingPick, pick_id)
    if row is None:
        raise HTTPException(404, "Reading pick not found")
    if row.teacher_id != user.id and user.role not in ("school_admin",
                                                       "platform_admin"):
        raise HTTPException(403, "Not your pick")
    session.delete(row)
    session.commit()
    return {"deleted": pick_id}
