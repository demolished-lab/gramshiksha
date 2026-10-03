from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, or_, select

from ..db import get_session
from ..models import Board, Chapter, Course, Enrollment, Lesson, Subject, Textbook, User
from ..ncert import chapter_exists, fetch_ncert_chapter, ncert_code
from ..ratelimit import rate_limit
from ..security import get_current_user, require_student
from ..streams import STREAM_CODES, STREAMS

router = APIRouter(tags=["catalog"])

# Medium label per language code — shown on explore chips so a book's
# language reads as a real medium name (Marathi-medium, Urdu-medium, …).
MEDIUM_LABELS = {
    "en": "English", "hi": "हिंदी", "mr": "मराठी", "ur": "اردو",
    "gu": "ગુજરાતી", "ta": "தமிழ்", "te": "తెలుగు", "kn": "ಕನ್ನಡ",
    "ml": "മലയാളം", "bn": "বাংলা", "od": "ଓଡ଼ିଆ", "pa": "ਪੰਜਾਬੀ",
    "as": "অসমীয়া", "ne": "नेपाली",
}


@router.get("/meta/boards")
def list_boards(session: Session = Depends(get_session)):
    rows = session.exec(select(Board)).all()
    return [{"id": b.id, "name": b.name} for b in rows] or [
        {"id": 1, "name": "Maharashtra SSC"}, {"id": 2, "name": "Maharashtra HSC"},
        {"id": 3, "name": "CBSE"}]


@router.get("/meta/subjects")
def list_subjects(class_grade: int = Query(..., ge=1, le=12), board: str = Query("CBSE"),
                  session: Session = Depends(get_session)):
    rows = session.exec(select(Subject).where(
        Subject.class_grade == class_grade, Subject.board == board)).all()
    return [{"id": s.id, "name_en": s.name_en, "name_hi": s.name_hi, "name_mr": s.name_mr,
             "stream": s.stream}
            for s in rows]


def _check_stream(stream: str) -> str:
    """Validate a ?stream= value — "" (all streams) or a known code."""
    if stream and stream not in STREAM_CODES:
        raise HTTPException(422, f"unknown stream: {stream}")
    return stream


def _stream_or_common(col, stream: str):
    """A stream filter never hides shared subjects: stream == X OR common."""
    return or_(col == stream, col == "")


@router.get("/catalog/availability")
def catalog_availability(
    board: str = Query(...),
    class_grade: int = Query(..., ge=1, le=12),
    session: Session = Depends(get_session),
):
    """Everything that actually exists for one (board, class) in one call.

    The UI renders medium chips, subject cards and every filter option from
    this response instead of fixed lists, so an offered combination can never
    be an empty result page: not every class publishes every medium's book in
    every subject, and this endpoint is where the app stops pretending.
    """
    books = session.exec(select(Textbook).where(
        Textbook.board == board, Textbook.class_grade == class_grade)).all()
    courses = session.exec(select(Course).where(
        Course.board == board, Course.class_grade == class_grade,
        Course.published == True)).all()  # noqa: E712

    subject_rows = session.exec(select(Subject).where(
        Subject.class_grade == class_grade, Subject.board == board)).all()
    tr_by_name = {s.name_en: s for s in subject_rows}

    subjects: dict[str, dict] = {}
    for b in books:
        row = subjects.setdefault(b.subject_name, {
            "name": b.subject_name, "name_hi": None, "name_mr": None,
            "subject_id": None, "books_by_lang": {}, "courses": 0,
            "lessons": 0, "course_ids": [],
            "stream": b.stream if class_grade >= 11 else ""})
        row["books_by_lang"][b.lang] = row["books_by_lang"].get(b.lang, 0) + 1
        tr = tr_by_name.get(b.subject_name)
        if tr:
            row["name_hi"], row["name_mr"] = tr.name_hi, tr.name_mr
            row["subject_id"] = tr.id
            if class_grade >= 11 and tr.stream:
                row["stream"] = tr.stream

    # Courses carry a subject_id; resolve name + count chapters/lessons so a
    # subject card can honestly say "12 lessons" or show nothing at all.
    course_ids = [c.id for c in courses if c.id is not None]
    lesson_by_course: dict[int, int] = {}
    if course_ids:
        chapters = session.exec(select(Chapter).where(
            Chapter.course_id.in_(course_ids))).all()
        chapter_ids = [c.id for c in chapters if c.id is not None]
        if chapter_ids:
            lessons = session.exec(select(Lesson).where(
                Lesson.chapter_id.in_(chapter_ids),
                Lesson.published == True)).all()  # noqa: E712
            chapter_course = {c.id: c.course_id for c in chapters}
            for les in lessons:
                cid = chapter_course.get(les.chapter_id)
                if cid is not None:
                    lesson_by_course[cid] = lesson_by_course.get(cid, 0) + 1
    for c in courses:
        subj = session.get(Subject, c.subject_id)
        if not subj:
            continue
        row = subjects.setdefault(subj.name_en, {
            "name": subj.name_en, "name_hi": subj.name_hi, "name_mr": subj.name_mr,
            "subject_id": subj.id, "books_by_lang": {}, "courses": 0,
            "lessons": 0, "course_ids": [],
            "stream": subj.stream if class_grade >= 11 else ""})
        row["subject_id"] = row["subject_id"] or subj.id
        row["courses"] += 1
        row["lessons"] += lesson_by_course.get(c.id, 0)
        row["course_ids"].append(c.id)

    lang_books: dict[str, int] = {}
    lang_subjects: dict[str, set] = {}
    for b in books:
        lang_books[b.lang] = lang_books.get(b.lang, 0) + 1
        lang_subjects.setdefault(b.lang, set()).add(b.subject_name)
    mediums = [{"lang": code, "label": MEDIUM_LABELS.get(code, code.upper()),
                "books": lang_books[code], "subjects": len(lang_subjects[code])}
               for code in sorted(lang_books)]

    # Streams actually present here (11-12 only — younger classes get [] and
    # the UI keeps its flat subject list). Counts include common books, so
    # a chip never advertises an empty stream.
    stream_books: dict[str, int] = {}
    if class_grade >= 11:
        for b in books:
            if b.stream:
                stream_books[b.stream] = stream_books.get(b.stream, 0) + 1
    common = len(books)
    streams = [{"code": code, "label_en": en, "books": stream_books.get(code, 0) + common}
               for code, en, _hi, _mr in STREAMS if code in stream_books]

    return {
        "board": board,
        "class_grade": class_grade,
        "mediums": mediums,
        "streams": streams,
        "subjects": sorted(subjects.values(), key=lambda s: s["name"]),
    }


@router.get("/courses")
def list_courses(
    class_grade: Optional[int] = Query(None, ge=1, le=12),
    board: Optional[str] = None,
    subject_id: Optional[int] = None,
    lang: Optional[str] = None,
    difficulty: Optional[str] = None,
    stream: str = "",
    free_only: bool = False,
    sort: str = Query("popular", pattern="^(popular|newest|rating|shortest|longest)$"),
    limit: int = Query(20, le=100),
    offset: int = 0,
    session: Session = Depends(get_session),
):
    q = select(Course).where(Course.published == True)  # noqa: E712
    if class_grade:
        q = q.where(Course.class_grade == class_grade)
    if board:
        q = q.where(Course.board == board)
    if subject_id:
        q = q.where(Course.subject_id == subject_id)
    if _check_stream(stream):
        # Courses inherit their stream from their Subject — shared subjects
        # (stream "") stay visible under every stream.
        q = q.join(Subject, Course.subject_id == Subject.id).where(
            _stream_or_common(Subject.stream, stream))
    if lang:
        q = q.where(Course.lang == lang)
    if difficulty:
        q = q.where(Course.difficulty == difficulty)
    if free_only:
        q = q.where(Course.is_free == True)  # noqa: E712
    order = {
        "popular": Course.students_count.desc(),
        "newest": Course.created_at.desc(),
        "rating": Course.rating.desc(),
        "shortest": Course.duration_min.asc(),
        "longest": Course.duration_min.desc(),
    }[sort]
    rows = session.exec(q.order_by(order).offset(offset).limit(limit)).all()
    from sqlmodel import func
    count_q = select(func.count()).select_from(Course).where(Course.published == True)  # noqa: E712
    if class_grade:
        count_q = count_q.where(Course.class_grade == class_grade)
    if board:
        count_q = count_q.where(Course.board == board)
    if subject_id:
        count_q = count_q.where(Course.subject_id == subject_id)
    if _check_stream(stream):
        count_q = count_q.join(Subject, Course.subject_id == Subject.id).where(
            _stream_or_common(Subject.stream, stream))
    if lang:
        count_q = count_q.where(Course.lang == lang)
    if difficulty:
        count_q = count_q.where(Course.difficulty == difficulty)
    if free_only:
        count_q = count_q.where(Course.is_free == True)  # noqa: E712
    # SQLAlchemy may return no scalar row for an empty filtered result set
    # (notably with SQLite), so an empty catalog must remain a valid response.
    total = session.exec(count_q).one_or_none() or 0
    subjects = {s.id: s.stream for s in session.exec(
        select(Subject).where(Subject.id.in_(
            {c.subject_id for c in rows}))).all()} if rows else {}
    return {"total": total, "items": [
        _course_out(c, subjects.get(c.subject_id, "")) for c in rows]}


def _course_out(c: Course, stream: str = "") -> dict:
    return {
        "id": c.id, "slug": c.slug, "title_en": c.title_en, "title_hi": c.title_hi,
        "title_mr": c.title_mr, "desc_en": c.desc_en, "desc_hi": c.desc_hi,
        "desc_mr": c.desc_mr, "board": c.board, "class_grade": c.class_grade,
        "subject_id": c.subject_id, "stream": stream, "lang": c.lang, "difficulty": c.difficulty,
        "duration_min": c.duration_min, "rating": c.rating,
        "ratings_count": c.ratings_count, "students_count": c.students_count,
        "is_free": c.is_free, "thumb_color": c.thumb_color, "teacher_id": c.teacher_id,
    }


@router.get("/courses/{course_id}")
def get_course(course_id: int, session: Session = Depends(get_session)):
    c = session.get(Course, course_id)
    if not c or not c.published:
        raise HTTPException(404, "Course not found")
    from ..models import Chapter, Lesson
    chapters = session.exec(select(Chapter).where(
        Chapter.course_id == course_id).order_by(Chapter.order)).all()
    out = _course_out(c)
    chs = []
    for ch in chapters:
        lessons = session.exec(
            select(Lesson).where(
                Lesson.chapter_id == ch.id, Lesson.published == True)  # noqa: E712
            .order_by(Lesson.order)).all()
        chs.append({
            "id": ch.id, "order": ch.order, "title_en": ch.title_en,
            "title_hi": ch.title_hi, "title_mr": ch.title_mr,
            "lessons": [{"id": les.id, "order": les.order, "type": les.type,
                         "title_en": les.title_en, "title_hi": les.title_hi,
                         "title_mr": les.title_mr, "duration_min": les.duration_min,
                         "estimate_mb": les.estimate_mb} for les in lessons],
        })
    out["chapters"] = chs
    return out


@router.post("/courses/{course_id}/enroll", status_code=201)
def enroll(course_id: int, user: User = Depends(require_student),
           session: Session = Depends(get_session)):
    if not session.get(Course, course_id):
        raise HTTPException(404, "Course not found")
    existing = session.exec(select(Enrollment).where(
        Enrollment.user_id == user.id, Enrollment.course_id == course_id)).first()
    if existing:
        return {"ok": True, "already": True}
    session.add(Enrollment(user_id=user.id, course_id=course_id))
    course = session.get(Course, course_id)
    if course:
        course.students_count += 1
        session.add(course)
    session.commit()
    return {"ok": True}


@router.get("/my/courses")
def my_courses(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    rows = session.exec(select(Enrollment).where(Enrollment.user_id == user.id)).all()
    out = []
    for e in rows:
        c = session.get(Course, e.course_id)
        if c:
            item = _course_out(c)
            item["progress_pct"] = e.progress_pct
            out.append(item)
    return out


@router.get("/textbooks/portals")
def textbook_portals():
    """Official portals only — frontend fallback when a filter has no rows."""
    return [
        {"name": "ePathshala (NCERT, CBSE)", "url": "https://epathshala.nic.in/process.php?id=students&type=eTextbooks&ln=en",
         "boards": ["CBSE"], "langs": ["en", "hi"]},
        {"name": "NCERT textbooks", "url": "https://ncert.nic.in/textbook.php",
         "boards": ["CBSE"], "langs": ["en", "hi"]},
        {"name": "eBalbharati (Maharashtra SSC/HSC)", "url": "https://books.ebalbharati.in",
         "boards": ["Maharashtra SSC", "Maharashtra HSC"], "langs": ["mr", "en", "hi"]},
    ]


@router.get("/textbooks/coverage")
def textbooks_coverage(session: Session = Depends(get_session)):
    """Counts per board/grade so the UI can show what is available."""
    from ..models import Textbook as _TB
    rows = session.exec(select(_TB)).all()
    cov: dict[str, dict[int, int]] = {}
    for t in rows:
        cov.setdefault(t.board, {}).setdefault(t.class_grade, 0)
        cov[t.board][t.class_grade] += 1
    return cov


@router.get("/textbooks")
def textbooks(class_grade: int = Query(..., ge=1, le=12), board: str = Query(...),
              subject_name: Optional[str] = None, lang: Optional[str] = None,
              stream: str = "",
              session: Session = Depends(get_session)):
    q = select(Textbook).where(Textbook.class_grade == class_grade, Textbook.board == board)
    if subject_name:
        q = q.where(Textbook.subject_name == subject_name)
    if lang:
        q = q.where(Textbook.lang == lang)
    if _check_stream(stream):
        q = q.where(_stream_or_common(Textbook.stream, stream))
    rows = session.exec(q.order_by(Textbook.subject_name, Textbook.lang)).all()
    return [_textbook_out(t) for t in rows]


def _cover_cdn(url: str) -> str:
    """Rewrite an origin cover URL through Cloudinary's transform CDN.

    eBalbharati's BookCovers endpoint sends no Cache-Control and ~0.3s TTFB;
    a library page pulls a dozen covers at once. f_auto/q_auto/w_360 serves
    them as edge-cached WebP at a fraction of the size — the first viewer
    pays the origin fetch, everyone after hits the CDN. Returns the origin
    URL untouched when Cloudinary isn't configured (local dev / tests)."""
    if not url or not url.startswith("http"):
        return url
    try:
        from urllib.parse import quote
        from ..config import settings
        if not settings.cloudinary_cloud_name:
            return url
        return (f"https://res.cloudinary.com/{settings.cloudinary_cloud_name}"
                f"/image/fetch/f_auto,q_auto,w_360/"
                f"{quote(url, safe='')}")
    except Exception:
        return url


def _textbook_out(t: Textbook) -> dict:
    return {"id": t.id, "title": t.title, "board": t.board, "class_grade": t.class_grade,
            "subject_name": t.subject_name, "stream": t.stream, "lang": t.lang, "source_url": t.source_url,
            "publisher": t.publisher, "has_deep_link": bool(t.deep_url and t.last_ok),
            "has_chapters": bool(t.board == "CBSE"
                                 and ncert_code(t.class_grade, t.subject_name, t.lang)),
            "cover_url": _cover_cdn(t.cover_url) or None,
            "part_label": t.part_label or None, "clicks": t.clicks}


def check_url(url: str, timeout_s: float = 15.0) -> bool:
    """Polite link check: HEAD, falling back to a 1-byte ranged GET."""
    import httpx
    try:
        r = httpx.head(url, timeout=timeout_s, follow_redirects=True,
                       headers={"User-Agent": "GramShiksha-linkcheck/1.0"})
        if r.status_code == 405:
            r = httpx.get(url, timeout=timeout_s, follow_redirects=True,
                          headers={"User-Agent": "GramShiksha-linkcheck/1.0",
                                   "Range": "bytes=0-0"})
        return r.status_code < 400
    except Exception:
        return False


# The proxy never buffers an unbounded body: 60 MB is far above any real
# textbook (eB books are 3–15 MB) and keeps one bad URL from eating the
# free-tier instance's 512 MB.
PDF_MAX_BYTES = 60 * 1024 * 1024
PDF_TIMEOUT_S = 30.0
UA = "GramShiksha-book/1.0"


def _fetch_pdf(url: str) -> Optional[bytes]:
    """Download an official PDF server-side, or None when it won't serve one.

    This is the whole point of /open: the student's browser stays on our
    origin and only ever sees the final result (the PDF), never a visible
    bounce through books.ebalbharati.in / epathshala.nic.in. `url` comes from
    a verified `deep_url` row — never from request input — so this cannot be
    pointed at anything but a link our own crawler HEAD-checked.
    """
    import httpx
    try:
        with httpx.stream("GET", url, timeout=PDF_TIMEOUT_S, follow_redirects=True,
                          headers={"User-Agent": UA}) as r:
            if r.status_code != 200:
                return None
            ctype = r.headers.get("content-type", "").lower()
            # Portals disagree about the header; a .pdf path counts as intent.
            if "pdf" not in ctype and "octet-stream" not in ctype \
                    and not url.split("?")[0].lower().endswith(".pdf"):
                return None
            chunks: list[bytes] = []
            total = 0
            for chunk in r.iter_bytes():
                total += len(chunk)
                if total > PDF_MAX_BYTES:
                    return None  # refuse rather than melt the instance
                chunks.append(chunk)
        data = b"".join(chunks)
        # PDF spec: %PDF lives in the first 1024 bytes. A 200 HTML error page
        # (soft-404) must never be handed to a viewer as a "PDF".
        return data if b"%PDF" in data[:1024] else None
    except Exception:
        return None


def _pdf_disposition(title: str, inline: bool) -> str:
    """RFC 6266 filename from a Devanagari title: an ASCII fallback for old
    clients plus `filename*=UTF-8''…` so the saved file keeps its real name."""
    from urllib.parse import quote
    import re as _re
    safe = _re.sub(r'[\\/:*?"<>|\x00-\x1f]+', " ", title or "").strip() or "textbook"
    ascii_name = safe.encode("ascii", "ignore").decode() or "textbook"
    kind = "inline" if inline else "attachment"
    return (f'{kind}; filename="{ascii_name[:80]}.pdf"; '
            f"filename*=UTF-8''{quote(safe[:80])}.pdf")


@router.get("/textbooks/{textbook_id}/open",
            dependencies=[Depends(rate_limit("catalog.open", 30, 60.0))])
def open_textbook(textbook_id: int,
                  dl: int = Query(0),      # 1 → attachment (Save, not view)
                  ext: int = Query(0),      # 1 → legacy 302 to the publisher
                  chapter: int = Query(0, ge=0, le=99),  # N ≥ 1 → NCERT chapter N
                  session: Session = Depends(get_session)):
    """Open a book **without leaving the site**.

    Default: fetch the verified deep PDF on the server and stream it back
    from our own origin, so the browser renders the final document in the
    in-app viewer instead of visibly redirecting to a government portal.
    Query switches keep every older behaviour reachable:
      `?dl=1`  same bytes, `Content-Disposition: attachment` (Save file)
      `?ext=1` explicit "open on the publisher's site" → the old 302
      `?chapter=N` an NCERT chapter edition (CBSE books with a verified code
        only) — each chapter is HEAD-verified live before proxying, and a
        missing chapter is an honest 404, never a redirect.
    Fallbacks still redirect (inside the iframe, so nothing visibly moves):
    no healthy deep link → the portal page; a proxy failure → the deep URL.

    The click is counted either way — analytics and dead-link management
    (see /admin/textbooks/recheck) survive the proxy."""
    from fastapi.responses import RedirectResponse, Response
    t = session.get(Textbook, textbook_id)
    if not t:
        raise HTTPException(404, "Textbook not found")
    t.clicks += 1
    session.add(t)
    session.commit()
    kind, payload = _resolve_open(textbook_id, dl, ext, chapter, session)
    if kind == "miss":
        raise HTTPException(404, payload)
    if kind == "redirect":
        return RedirectResponse(payload, status_code=302)
    data, title = payload
    return Response(
        content=data, media_type="application/pdf",
        headers={
            "Content-Disposition": _pdf_disposition(title, inline=not dl),
            # private: student traffic must not be parked in a shared cache.
            "Cache-Control": "private, max-age=300",
            "X-Content-Type-Options": "nosniff",
            # The in-app viewer frames this from our own origin (/api is a
            # Vercel same-origin rewrite). The global DENY would blank that
            # frame, so relax it — to same-origin only, never to anybody.
            "X-Frame-Options": "SAMEORIGIN",
            "Content-Security-Policy": "frame-ancestors 'self'",
        })


@router.head("/textbooks/{textbook_id}/open",
             dependencies=[Depends(rate_limit("catalog.open", 30, 60.0))])
def open_textbook_head(textbook_id: int,
                       dl: int = Query(0),
                       ext: int = Query(0),
                       chapter: int = Query(0, ge=0, le=99),
                       session: Session = Depends(get_session)):
    """Existence probe for the chapter pager: same resolution as GET, headers
    only, no bytes, no click counted. The reader HEADs chapter N+1 before
    paging — a 404 clamps the pager at the last chapter instead of opening
    an error page."""
    from fastapi.responses import Response
    if chapter:
        # Pager probe: existence only, no bytes, no click. A past-end chapter
        # is 404 so the pager clamps instead of opening an error page.
        t = session.get(Textbook, textbook_id)
        code = (ncert_code(t.class_grade, t.subject_name, t.lang)
                if t is not None and t.board == "CBSE" else None)
        if code is None or not chapter_exists(code, chapter):
            raise HTTPException(404, "No such chapter edition")
        return Response(status_code=200, media_type="application/pdf")
    kind, payload = _resolve_open(textbook_id, dl, ext, chapter, session)
    if kind == "miss":
        raise HTTPException(404, payload)
    if kind == "redirect":
        # A redirect target exists (portal page / deep URL) — the resource
        # the reader asked about is reachable.
        return Response(status_code=200)
    data, title = payload
    return Response(
        status_code=200, media_type="application/pdf",
        headers={
            "Content-Disposition": _pdf_disposition(title, inline=not dl),
            "Content-Length": str(len(data)),
        })


def _resolve_open(textbook_id: int, dl: int, ext: int, chapter: int,
                  session: Session):
    """Shared resolution for GET and HEAD: returns ("pdf", (data, title)) or
    ("redirect", url) or ("miss", message). Click counting stays with the
    GET caller — a HEAD probe must not inflate analytics."""
    t = session.get(Textbook, textbook_id)
    if not t:
        return ("miss", "Textbook not found")
    if chapter:
        # CBSE chapter edition: only books whose NCERT code was verified live
        # (see app/ncert.py) — anything else is an honest 404, and the reader
        # treats that as "no further chapters".
        code = (ncert_code(t.class_grade, t.subject_name, t.lang)
                if t.board == "CBSE" else None)
        data = fetch_ncert_chapter(code, chapter) if code else None
        if data is None:
            return ("miss", "No such chapter edition")
        return ("pdf", (data, f"{t.title} ch{chapter}"))
    deep = t.deep_url if (t.deep_url and t.last_ok) else None
    if not deep:
        # Nothing to proxy: source_url is the portal *page*, not a PDF.
        return ("redirect", t.source_url)
    if ext:
        return ("redirect", deep)
    data = _fetch_pdf(deep)
    if data is None:
        # Publisher down/slow/changed its mind — fall through to the source,
        # still inside this frame. Rare by construction (deep links are
        # re-verified), but a broken button helps nobody.
        return ("redirect", deep)
    return ("pdf", (data, t.title))
