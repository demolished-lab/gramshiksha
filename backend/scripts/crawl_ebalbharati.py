"""Crawl the OFFICIAL eBalbharati e-book library and map books to Textbook rows.

Official sources only — this is exactly the portal GramShiksha links to.
Social platforms / random PDF mirrors are deliberately NOT crawled (copyright).

How it works (verified Sep 2026 against the live site):
  - https://books.ebalbharati.in/ is ASP.NET WebForms. Filters post back with
    __EVENTTARGET=upBtn / upMain and __EVENTARGUMENT="<filterIds>#<page>".
  - Filter codes: type 101=Text Books; classes 201..212 = 1st..12th;
    mediums 301=Marathi 302=Hindi 303=English 304=Urdu 305=Gujarati
    306=Kannad 307=Sindhi 309=Telugu 310=Tamil 311=Bengali.
  - Each hit embeds: SaveToDisk("https://ebooks.ebalbharati.in/pdfs/<ID>.pdf",...)
    plus a title div and BookCovers/<ID>.jpg.
  - Deep PDFs verified live: GET /pdfs/101050001.pdf -> 200 application/pdf.

Usage:
  python scripts/crawl_ebalbharati.py --classes 1 2 3 --mediums 301 302 303
      --output catalog.json            # crawl only, no DB writes
  python scripts/crawl_ebalbharati.py --apply   # + fill deep_url/cover_url
      # on high-confidence (board, grade, subject, lang) matches only

Needs: httpx (in requirements.txt). Polite by default (1.5s between requests).
If the postback contract ever breaks, fall back to a headless pass
(obscura / crawl4ai render the same pages and expose the SaveToDisk calls).

Env: DATABASE_URL (default local gramshiksha.db) — only used with --apply.
"""
import argparse
import json
import re
import sys
import time
from html import unescape

import httpx

BASE = "https://books.ebalbharati.in/"
UA = {"User-Agent": "GramShiksha-catalog-crawl/1.0 (official-portal inventory; polite)"}

MEDIUM_LANG = {"301": "mr", "302": "hi", "303": "en", "304": "ur",
               "305": "gu", "306": "kn", "307": "sd", "309": "te",
               "310": "ta", "311": "bn"}
# Medium is also encoded in book-ID digits 2-3 (verified live: 101..=Marathi,
# 102..=Hindi, 103..=English). The ID wins over filter context — the portal's
# medium filter is fuzzy (e.g. English titles surface under medium=301).
ID_MEDIUM = {"01": "mr", "02": "hi", "03": "en", "04": "ur", "05": "gu",
             "06": "kn", "07": "sd", "09": "te", "10": "ta", "11": "bn"}
CLASS_GRADE = {f"{200 + g}": g for g in range(1, 13)}

# title keyword -> our subject_name (checked per lang where keywords differ)
SUBJECT_KEYWORDS = [
    ("Mathematics", ["गणित", "गणितम्", "mathematics", "math", "गणित "]),
    ("Science", ["विज्ञान", "science", "सामान्य विज्ञान"]),
    ("History", ["इतिहास", "history"]),
    ("Geography", ["भूगोल", "geography"]),
    ("Civics", ["नागरिकशास्त्र", "civics", "राज्यशास्त्र"]),
    ("Physics", ["भौतिक", "physics"]),
    ("Chemistry", ["रसायन", "chemistry"]),
    ("Biology", ["जीव", "biology", "वनस्पती"]),
    ("Computer Science", ["संगणक", "computer", "माहिती तंत्रज्ञान"]),
    ("Environmental Studies", ["परिसर अभ्यास", "सभोवताल", "environmental", "पर्यावरण"]),
    ("English", ["इंग्रजी", "इंग्लिश", "english"]),
    ("Hindi", ["हिंदी", "hindi"]),
    ("Marathi", ["मराठी", "marathi", "बालभारती"]),
]

ID_RE = re.compile(r'SaveToDisk\("https://ebooks\.ebalbharati\.in/pdfs/(\d+)\.pdf"')
TITLE_RE = re.compile(r"class=divbooknm title='([^']*)'")
PAGES_RE = re.compile(r'id="lblNoOfPages"[^>]*>(\d+)<')
INPUT_RE = re.compile(r'<input[^>]+name="([^"]+)"[^>]*value="([^"]*)"')
INPUT_RE2 = re.compile(r'<input[^>]+value="([^"]*)"[^>]*name="([^"]+)"')


def hidden_fields(html: str) -> dict:
    fields: dict[str, str] = {}
    for m in INPUT_RE.finditer(html):
        fields[m.group(1)] = unescape(m.group(2))
    for m in INPUT_RE2.finditer(html):
        fields.setdefault(m.group(2), unescape(m.group(1)))
    return fields


def parse_hits(html: str) -> list[tuple[str, str]]:
    ids = ID_RE.findall(html)
    titles = [unescape(t) for t in TITLE_RE.findall(html)]
    return list(zip(ids, titles))


def crawl(client: httpx.Client, year: str, ftype: str, class_code: str,
          medium_code: str, delay: float, max_pages: int = 0) -> list[tuple[str, str]]:
    r = client.get(BASE, timeout=30)
    r.raise_for_status()
    form = hidden_fields(r.text)
    filt = f"{class_code} {medium_code}"

    def post(target: str, arg: str) -> str:
        payload = dict(form)
        payload.update({"__EVENTTARGET": target, "__EVENTARGUMENT": arg,
                        "txtSelected": filt, "txtyear": year})
        time.sleep(delay)
        resp = client.post(BASE, data=payload, timeout=30)
        resp.raise_for_status()
        return resp.text

    html = post("upBtn", f"{filt}#1")
    hits = parse_hits(html)
    m = PAGES_RE.search(html)
    pages = int(m.group(1)) if m else 1
    if max_pages:
        pages = min(pages, max_pages)
    for p in range(2, pages + 1):
        hits += parse_hits(post("upMain", f"{filt}#{p}"))
    # de-dupe, keep order
    seen: set[str] = set()
    out = []
    for bid, title in hits:
        if bid not in seen:
            seen.add(bid)
            out.append((bid, title))
    return out


# Trailing medium words pollute subject matching (e.g. "समाजशास्त्र मराठी"
# would false-match Marathi). Strip before guessing — verified live 2026.
MEDIUM_WORDS = ["मराठी", "हिंदी", "हिन्दी", "इंग्रजी", "इंग्लिश", "english",
                "उर्दु", "गुजराती", "कन्नड", "सिंधी", "तेलुगु", "तामिळ", "बंगाली"]


def strip_medium(title: str) -> str:
    t = title.strip()
    low = t.lower()
    for w in MEDIUM_WORDS:
        if low.endswith(w.lower()):
            return t[: -len(w)].strip()
    return t


def lang_from_id(book_id: str, grade: int, fallback: str = "") -> str:
    """Medium is 2 digits after the class prefix (1 digit below class 10,
    2 digits from class 10 up — verified: 101..=1st/Marathi, 1001..=10th,
    1201..=12th/Marathi)."""
    pre = 2 if grade >= 10 else 1
    return ID_MEDIUM.get(book_id[pre:pre + 2], fallback)


def guess_subject(title: str, lang: str = "") -> str:
    t = strip_medium(title)
    # Std 11-12 language books are all titled "Yuvakbharati" — the language
    # comes from the medium, not the title (verified against live catalog).
    if "युवकभारती" in t:
        return {"mr": "Marathi", "hi": "Hindi", "en": "English"}.get(lang, "")
    low = t.lower()
    for subj, keys in SUBJECT_KEYWORDS:
        if any(k.lower() in low for k in keys):
            return subj
    return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", default="2026")
    ap.add_argument("--type", default="101")
    ap.add_argument("--classes", nargs="+",
                    default=[str(c) for c in range(201, 213)])
    ap.add_argument("--mediums", nargs="+", default=["301", "302", "303"])
    ap.add_argument("--delay", type=float, default=1.5)
    ap.add_argument("--max-pages", type=int, default=0)
    ap.add_argument("--output", default="ebalbharati_catalog.json")
    ap.add_argument("--input", default="",
                    help="use an existing catalog JSON instead of crawling")
    ap.add_argument("--apply", action="store_true",
                    help="fill deep_url/cover_url on exact Textbook matches")
    ap.add_argument("--audit", action="store_true",
                    help="revert applied deep_urls whose recomputed guess no "
                         "longer matches the row's subject (matcher upgrades)")
    ap.add_argument("--board", default="Maharashtra SSC",
                    help="board to match rows against with --apply "
                         "(run twice for SSC/HSC), or 'auto' for "
                         "SSC in grades 1-10 and HSC in 11-12")
    args = ap.parse_args()

    catalog: list[dict] = []
    if args.input:
        with open(args.input, encoding="utf-8") as f:
            catalog = json.load(f)
        for c in catalog:  # recompute with current keywords, not crawl-time ones
            lang = c.get("lang") or lang_from_id(
                c.get("book_id", ""), c.get("grade", 0), "")
            c["lang"] = lang
            c["subject_guess"] = guess_subject(c.get("title", ""), lang)
        print(f"loaded {len(catalog)} entries from {args.input}")
    else:
        with httpx.Client(headers=UA) as client:
            for cc in args.classes:
                for mc in args.mediums:
                    try:
                        hits = crawl(client, args.year, args.type, cc, mc,
                                     args.delay, args.max_pages)
                    except Exception as exc:  # noqa: BLE001 — keep crawling rest
                        print(f"WARN {cc}/{mc}: {exc}", flush=True)
                        continue
                    grade = CLASS_GRADE.get(cc, 0)
                    for bid, title in hits:
                        lang = lang_from_id(bid, grade, MEDIUM_LANG.get(mc, ""))
                        catalog.append({"book_id": bid, "title": title,
                                        "grade": grade, "lang": lang,
                                        "subject_guess": guess_subject(title, lang),
                                        "pdf": f"https://ebooks.ebalbharati.in/pdfs/{bid}.pdf",
                                        "cover": f"https://books.ebalbharati.in/BookCovers/{bid}.jpg"})
                    print(f"{cc}/{mc}: {len(hits)} books", flush=True)

        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(catalog, f, ensure_ascii=False, indent=1)
        print(f"wrote {len(catalog)} entries -> {args.output}")

    if args.audit:
        return audit_applied(catalog)
    if args.apply:
        return apply_catalog(catalog, args.board)
    unmatched = sum(1 for c in catalog if not c["subject_guess"])
    print(f"subject unmatched: {unmatched} (review before --apply)")
    return 0


def audit_applied(catalog: list[dict]) -> int:
    """Revert deep_urls applied under an older, buggier matcher.

    A row is reverted when the current guess for its stored PDF no longer
    equals the row's own (board, grade, subject, lang). Safe + idempotent.
    """
    sys.path.insert(0, "backend")
    from sqlmodel import Session, select
    from app.db import engine, ensure_textbook_columns
    from app.models import Textbook

    ensure_textbook_columns()
    by_pdf = {c["pdf"]: c for c in catalog}
    reverted = kept = 0
    with Session(engine) as s:
        rows = s.exec(select(Textbook).where(Textbook.deep_url != "")).all()
        for row in rows:
            c = by_pdf.get(row.deep_url)
            if c is None:
                continue  # not crawler-sourced; leave alone
            use_board = ("Maharashtra HSC" if c["grade"] >= 11
                         else "Maharashtra SSC")
            good = (row.board == use_board and row.class_grade == c["grade"]
                    and row.subject_name == c["subject_guess"]
                    and row.lang == c["lang"] and c["subject_guess"])
            if good:
                kept += 1
            else:
                row.deep_url = ""
                row.cover_url = ""
                row.last_ok = True
                row.last_checked = None
                s.add(row)
                reverted += 1
                print(f"reverted: {row.board} g{row.class_grade} "
                      f"{row.subject_name} {row.lang} <- {row.deep_url}")
        s.commit()
    print(f"audit: kept {kept}, reverted {reverted}")
    return 0


def apply_catalog(catalog: list[dict], board: str) -> int:
    sys.path.insert(0, "backend")
    from sqlmodel import Session, select
    from app.db import engine, ensure_textbook_columns
    from app.models import Textbook

    ensure_textbook_columns()
    applied = skipped = 0
    with Session(engine) as s:
        for c in catalog:
            if not c["subject_guess"] or not c["grade"] or not c["lang"]:
                skipped += 1
                continue
            use_board = ("Maharashtra HSC" if c["grade"] >= 11
                         else "Maharashtra SSC") if board == "auto" else board
            row = s.exec(select(Textbook).where(
                Textbook.board == use_board, Textbook.class_grade == c["grade"],
                Textbook.subject_name == c["subject_guess"],
                Textbook.lang == c["lang"])).first()
            if row is None or row.deep_url:
                skipped += 1
                continue
            row.deep_url = c["pdf"]
            row.cover_url = c["cover"]
            row.last_ok = True
            row.last_checked = None  # recheck endpoint verifies on demand
            s.add(row)
            applied += 1
        s.commit()
    print(f"applied {applied}, skipped {skipped} (board={board})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
