from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from ..db import get_session
from ..models import Board, Chapter, Course, Enrollment, Lesson, Subject, Textbook, User
from ..security import get_current_user, require_student

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
    return [{"id": s.id, "name_en": s.name_en, "name_hi": s.name_hi, "name_mr": s.name_mr}
            for s in rows]


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
            "lessons": 0, "course_ids": []})
        row["books_by_lang"][b.lang] = row["books_by_lang"].get(b.lang, 0) + 1
        tr = tr_by_name.get(b.subject_name)
        if tr:
            row["name_hi"], row["name_mr"] = tr.name_hi, tr.name_mr
            row["subject_id"] = tr.id

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
            "lessons": 0, "course_ids": []})
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

    return {
        "board": board,
        "class_grade": class_grade,
        "mediums": mediums,
        "subjects": sorted(subjects.values(), key=lambda s: s["name"]),
    }


@router.get("/courses")
def list_courses(
    class_grade: Optional[int] = Query(None, ge=1, le=12),
    board: Optional[str] = None,
    subject_id: Optional[int] = None,
    lang: Optional[str] = None,
    difficulty: Optional[str] = None,
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
    if lang:
        count_q = count_q.where(Course.lang == lang)
    if difficulty:
        count_q = count_q.where(Course.difficulty == difficulty)
    if free_only:
        count_q = count_q.where(Course.is_free == True)  # noqa: E712
    total = session.exec(count_q).one()
    return {"total": total, "items": [_course_out(c) for c in rows]}


def _course_out(c: Course) -> dict:
    return {
        "id": c.id, "slug": c.slug, "title_en": c.title_en, "title_hi": c.title_hi,
        "title_mr": c.title_mr, "desc_en": c.desc_en, "desc_hi": c.desc_hi,
        "desc_mr": c.desc_mr, "board": c.board, "class_grade": c.class_grade,
        "subject_id": c.subject_id, "lang": c.lang, "difficulty": c.difficulty,
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
              session: Session = Depends(get_session)):
    q = select(Textbook).where(Textbook.class_grade == class_grade, Textbook.board == board)
    if subject_name:
        q = q.where(Textbook.subject_name == subject_name)
    if lang:
        q = q.where(Textbook.lang == lang)
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
            "subject_name": t.subject_name, "lang": t.lang, "source_url": t.source_url,
            "publisher": t.publisher, "has_deep_link": bool(t.deep_url and t.last_ok),
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


@router.get("/textbooks/{textbook_id}/open")
def open_textbook(textbook_id: int, session: Session = Depends(get_session)):
    """Wrapper redirect: counts the click, then 302s to the verified deep PDF
    link when healthy, otherwise falls back to the portal page.

    Note: this does NOT spare the official portal any load — the PDF bytes
    still download from ePathshala/eBalbharati. It buys click analytics and
    central dead-link management (see /admin/textbooks/recheck)."""
    from fastapi.responses import RedirectResponse
    t = session.get(Textbook, textbook_id)
    if not t:
        raise HTTPException(404, "Textbook not found")
    t.clicks += 1
    session.add(t)
    session.commit()
    target = t.deep_url if (t.deep_url and t.last_ok) else t.source_url
    return RedirectResponse(target, status_code=302)
