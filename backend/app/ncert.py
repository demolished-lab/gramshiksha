"""NCERT chapter editions for CBSE books.

Why this file exists: NCERT publishes whole books only as ~70 MB ZIPs
(over the proxy's 60 MB safety cap and hostile to the free tier), but every
chapter as a direct PDF at
`https://ncert.nic.in/textbook/pdf/{code}{NN}.pdf` — verified live, one by
one, with `pypdf` title-page checks on the samples (e.g. `jesc101.pdf` is
"SCIENCE TEXTBOOK FOR CLASS X", `lemh101.pdf` is "MATHEMATICS Class XII").
Only codes that returned HTTP 200 here are listed; everything else keeps
the honest Find/queue flow. `*ps.pdf` files are front-matter only and are
never used as reading targets.

Chapter counts differ per book and NCERT renumbers editions, so the count
is never stored — the reader discovers the last chapter live (a 404 means
"no further chapters") and each fetch is HEAD-verified before proxying,
exactly like the eBalbharati path.
"""

# (class_grade, subject_name, lang) -> NCERT book code. Verified live
# 2026-10-03 (HTTP 200 + application/pdf on chapter 01).
NCERT_CODES: dict[tuple[int, str, str], str] = {
    (7, "Science", "en"): "gesc1",
    (8, "Science", "en"): "hesc1",
    (8, "Mathematics", "en"): "hemh1",
    (9, "Science", "en"): "iesc1",
    (9, "Science", "hi"): "ihsc1",
    (9, "Mathematics", "en"): "iemh1",
    (9, "Mathematics", "hi"): "ihmh1",
    (10, "Science", "en"): "jesc1",
    (10, "Science", "hi"): "jhsc1",
    (10, "Mathematics", "en"): "jemh1",
    (10, "Mathematics", "hi"): "jhmh1",
    (11, "Mathematics", "en"): "kemh1",
    (11, "Physics", "en"): "keph1",
    (11, "Chemistry", "en"): "kech1",
    (11, "Biology", "en"): "kebo1",
    (12, "Mathematics", "en"): "lemh1",
    (12, "Physics", "en"): "leph1",
    (12, "Chemistry", "en"): "lech1",
    (12, "Biology", "en"): "lebo1",
}

NCERT_BASE = "https://ncert.nic.in/textbook/pdf"
NCERT_UA = "GramShiksha-book/1.0"
NCERT_TIMEOUT_S = 30.0
# Same ceiling as the eBalbharati proxy: refuse rather than melt the instance.
NCERT_MAX_BYTES = 60 * 1024 * 1024


def ncert_code(class_grade: int | None, subject_name: str, lang: str) -> str | None:
    """The NCERT book code for one catalog row, or None when unverified."""
    if not class_grade:
        return None
    return NCERT_CODES.get((class_grade, (subject_name or "").strip(), (lang or "").strip()))


def chapter_url(code: str, chapter: int) -> str:
    """Direct chapter PDF. Chapters are 2-digit: 01, 02, …"""
    return f"{NCERT_BASE}/{code}{chapter:02d}.pdf"


def fetch_ncert_chapter(code: str, chapter: int) -> bytes | None:
    """HEAD-verify then download one NCERT chapter, or None.

    Same honesty contract as the eBalbharati proxy: wrong content-type,
    oversize bodies and HTML-200 soft-404s all come back None so the caller
    answers 404 ("no such chapter") instead of serving junk.
    """
    import httpx

    if chapter < 1 or chapter > 99:
        return None
    url = chapter_url(code, chapter)
    try:
        head = httpx.head(url, timeout=NCERT_TIMEOUT_S, follow_redirects=True,
                           headers={"User-Agent": NCERT_UA})
        if head.status_code != 200:
            return None
        ctype = head.headers.get("content-type", "").lower()
        if "pdf" not in ctype and "octet-stream" not in ctype:
            return None
        with httpx.stream("GET", url, timeout=NCERT_TIMEOUT_S, follow_redirects=True,
                          headers={"User-Agent": NCERT_UA}) as r:
            if r.status_code != 200:
                return None
            chunks: list[bytes] = []
            total = 0
            for chunk in r.iter_bytes():
                total += len(chunk)
                if total > NCERT_MAX_BYTES:
                    return None
                chunks.append(chunk)
        data = b"".join(chunks)
        return data if b"%PDF" in data[:1024] else None
    except Exception:
        return None
