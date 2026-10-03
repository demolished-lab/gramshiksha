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

# (class_grade, subject_name.lower(), lang) -> NCERT book code. Every code
# returned HTTP 200 + application/pdf on its chapter 01; ambiguous mains
# were confirmed by title page (pypdf): Santoor/Veena/Maths-Mela (current
# NCF editions win over Marigold/Rimjhim/Math-Magic), Kaveri/Ganga/Ganita
# Manjari/Exploration (real current books), Part-I volumes (Political
# Theory over Constitution, Fundamentals over India volumes — title pages
# checked), First Flight over Foot Prints, Honeydew over It-So-Happened,
# Hornbill over Snapshots/Woven Words, Aroh over Antra/Vitan, Sparsh over
# Kshitij (canonical main reader), Kshitij-2 over Kritika. Single-option
# branches are self-validating (NCERT lists exactly one book). NOT mapped:
# grade-3 EVS (files absent), Marathi medium (never published), 9-10
# History/Geography (integrated SST book only — mapping both rows to one
# code would confuse), cross-medium seed noise beyond language subjects.
NCERT_CODES: dict[tuple[int, str, str], str] = {
    (4, "environmental studies", "en"): "deap1",
    (4, "environmental studies", "hi"): "dhap1",
    (5, "environmental studies", "en"): "eeap1",
    (5, "environmental studies", "hi"): "ehap1",
    (1, "mathematics", "en"): "aejm1",
    (1, "mathematics", "hi"): "ahjm1",
    (2, "mathematics", "en"): "bejm1",
    (2, "mathematics", "hi"): "bhjm1",
    (3, "mathematics", "en"): "cemm1",
    (3, "mathematics", "hi"): "chmm1",
    (4, "mathematics", "en"): "demm1",
    (4, "mathematics", "hi"): "dhmm1",
    (5, "mathematics", "en"): "eemm1",
    (5, "mathematics", "hi"): "ehmm1",
    (6, "mathematics", "en"): "fegp1",
    (6, "mathematics", "hi"): "fhgp1",
    (7, "mathematics", "en"): "gegp1",
    (7, "mathematics", "hi"): "ghgp1",
    (8, "mathematics", "en"): "hegp1",
    (8, "mathematics", "hi"): "hhgp1",
    (9, "mathematics", "en"): "iemh1",
    (9, "mathematics", "hi"): "ihmh1",
    (10, "mathematics", "en"): "jemh1",
    (10, "mathematics", "hi"): "jhmh1",
    (11, "mathematics", "en"): "kemh1",
    (11, "mathematics", "hi"): "khmh1",
    (12, "mathematics", "en"): "lemh1",
    (12, "mathematics", "hi"): "lhmh1",
    (6, "science", "en"): "fecu1",
    (6, "science", "hi"): "fhcu1",
    (7, "science", "en"): "gecu1",
    (7, "science", "hi"): "ghcu1",
    (8, "science", "en"): "hecu1",
    (8, "science", "hi"): "hhcu1",
    (9, "science", "en"): "iesc1",
    (9, "science", "hi"): "ihsc1",
    (10, "science", "en"): "jesc1",
    (10, "science", "hi"): "jhsc1",
    (2, "english", "en"): "bemr1",
    (3, "english", "en"): "cesa1",
    (4, "english", "en"): "desa1",
    (5, "english", "en"): "eesa1",
    (6, "english", "en"): "fepr1",
    (7, "english", "en"): "gepr1",
    (8, "english", "en"): "hehd1",
    (9, "english", "en"): "iebe1",
    (10, "english", "en"): "jeff1",
    (11, "english", "en"): "kehb1",
    (12, "english", "en"): "lefl1",
    (2, "english", "hi"): "bemr1",
    (3, "english", "hi"): "cesa1",
    (4, "english", "hi"): "desa1",
    (5, "english", "hi"): "eesa1",
    (6, "english", "hi"): "fepr1",
    (7, "english", "hi"): "gepr1",
    (8, "english", "hi"): "hehd1",
    (9, "english", "hi"): "iebe1",
    (10, "english", "hi"): "jeff1",
    (11, "english", "hi"): "kehb1",
    (12, "english", "hi"): "lefl1",
    (1, "hindi", "hi"): "ahsr1",
    (1, "hindi", "en"): "ahsr1",
    (2, "hindi", "hi"): "bhsr1",
    (2, "hindi", "en"): "bhsr1",
    (3, "hindi", "hi"): "chve1",
    (3, "hindi", "en"): "chve1",
    (4, "hindi", "hi"): "dhve1",
    (4, "hindi", "en"): "dhve1",
    (5, "hindi", "hi"): "ehve1",
    (5, "hindi", "en"): "ehve1",
    (6, "hindi", "hi"): "fhml1",
    (6, "hindi", "en"): "fhml1",
    (7, "hindi", "hi"): "ghml1",
    (7, "hindi", "en"): "ghml1",
    (8, "hindi", "hi"): "hhml1",
    (8, "hindi", "en"): "hhml1",
    (9, "hindi", "hi"): "ihga1",
    (9, "hindi", "en"): "ihga1",
    (10, "hindi", "hi"): "jhks1",
    (10, "hindi", "en"): "jhks1",
    (11, "hindi", "hi"): "khar1",
    (11, "hindi", "en"): "khar1",
    (12, "hindi", "hi"): "lhar1",
    (12, "hindi", "en"): "lhar1",
    (6, "social science", "en"): "fees1",
    (6, "social science", "hi"): "fhes1",
    (7, "social science", "en"): "gees1",
    (7, "social science", "hi"): "ghes1",
    (8, "social science", "en"): "hees1",
    (8, "social science", "hi"): "hhes1",
    (11, "physics", "en"): "keph1",
    (11, "chemistry", "en"): "kech1",
    (11, "biology", "en"): "kebo1",
    (11, "civics", "en"): "keps1",
    (11, "geography", "en"): "kegy2",
    (11, "history", "en"): "kehs1",
    (11, "computer science", "en"): "kecs1",
    (12, "physics", "en"): "leph1",
    (12, "chemistry", "en"): "lech1",
    (12, "biology", "en"): "lebo1",
    (12, "civics", "en"): "leps1",
    (12, "geography", "en"): "legy1",
    (12, "history", "en"): "lehs1",
    (12, "computer science", "en"): "lecs1",
}

NCERT_BASE = "https://ncert.nic.in/textbook/pdf"
# ncert.nic.in's edge drops non-browser clients at TCP level (verified:
# "GramShiksha-book/1.0" gets its connection reset while a browser UA gets
# 200) — so this endpoint identifies as a browser. Everything else about
# the fetch stays strict: HEAD-verified PDF, size cap, same-origin proxy.
NCERT_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
NCERT_TIMEOUT_S = 30.0
# Same ceiling as the eBalbharati proxy: refuse rather than melt the instance.
NCERT_MAX_BYTES = 60 * 1024 * 1024


def ncert_code(class_grade: int | None, subject_name: str, lang: str) -> str | None:
    """The NCERT book code for one catalog row, or None when unverified."""
    if not class_grade:
        return None
    return NCERT_CODES.get((class_grade, (subject_name or "").strip().lower(),
                            (lang or "").strip().lower()))


def chapter_url(code: str, chapter: int) -> str:
    """Direct chapter PDF. Chapters are 2-digit: 01, 02, …"""
    return f"{NCERT_BASE}/{code}{chapter:02d}.pdf"


def chapter_exists(code: str, chapter: int) -> bool:
    """Light existence probe: HEAD only, no bytes. What the pager's HEAD
    route calls before paging — a full download just to learn "yes" would
    burn the free tier for nothing."""
    import httpx

    if chapter < 1 or chapter > 99:
        return False
    try:
        head = httpx.head(chapter_url(code, chapter), timeout=NCERT_TIMEOUT_S,
                          follow_redirects=True,
                          headers={"User-Agent": NCERT_UA})
        if head.status_code != 200:
            return False
        ctype = head.headers.get("content-type", "").lower()
        return "pdf" in ctype or "octet-stream" in ctype
    except Exception:
        return False


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
