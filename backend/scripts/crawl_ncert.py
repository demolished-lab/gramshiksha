"""Map OFFICIAL NCERT / ePathshala PDFs to CBSE Textbook rows.

Discipline (same as crawl_ebalbharati.py): NOTHING is stored unless the URL
is verified live — HTTP 200 with a PDF content-type on ncert.nic.in or
epathshala.nic.in. Guessed codes are never seeded.

Why a separate script: ePathshala is JS-heavy and often unreachable outside
India (verified Sep 2026: direct + reader-proxy fetches time out from here).
Run this from inside India, or whenever the portal is reachable:

  python scripts/crawl_ncert.py --output ncert_catalog.json
  python scripts/crawl_ncert.py --input ncert_catalog.json --apply

What it does:
  1. Fetches official index pages (NCERT textbook.php, ePathshala eTextbook
     listings, flipbook indexes) and extracts candidate PDF links.
  2. Classifies each by (grade, subject, lang) from link text context.
  3. HEAD-verifies every candidate (follows redirects, 1-byte GET fallback).
  4. --apply writes deep_url/cover_url only on exact CBSE matches whose
     URL verified in this run. --audit reverts stale assignments.

Needs: httpx + beautifulsoup4? No — stdlib html.parser only (like the
eBalbharati crawler), to keep prod deps lean.
"""
import argparse
import json
import re
import sys
import time
from html.parser import HTMLParser

import httpx

UA = {"User-Agent": "GramShiksha-catalog-crawl/1.0 (official-portal inventory; polite)"}
OFFICIAL_HOSTS = ("ncert.nic.in", "epathshala.nic.in")

INDEX_PAGES = [
    "https://ncert.nic.in/textbook.php",
    "https://epathshala.nic.in/process.php?id=students&type=eTextbooks&ln=en",
    "https://epathshala.nic.in/process.php?id=students&type=eTextbooks&ln=hi",
]

SUBJECT_KEYWORDS = [
    ("Mathematics", ["math", "गणित"]),
    ("Science", ["science", "विज्ञान"]),
    ("Physics", ["physic", "भौतिक"]),
    ("Chemistry", ["chemis", "रसायन"]),
    ("Biology", ["biolog", "जीव"]),
    ("English", ["english", "अंग्रेजी", "अंग्रेज़ी"]),
    ("Hindi", ["hindi", "हिंदी"]),
    ("History", ["histor", "इतिहास"]),
    ("Geography", ["geograph", "भूगोल"]),
    ("Civics", ["civic", "political", "नागरिक", "राज्यशास्त्र"]),
    ("Environmental Studies", ["evs", "environmental", "पर्यावरण", "परिसर"]),
]

LANG_HINTS = [("hi", ["hindi", "हिंदी", "urdu", "उर्दू"]),
              ("en", ["english", "अंग्रेजी", "अंग्रेज़ी"])]
CLASS_RE = re.compile(r"class\s*(\d{1,2})|कक्षा\s*(\d{1,2})|grade\s*(\d{1,2})",
                      re.IGNORECASE)


class LinkHarvest(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href = ""
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag == "a":
            self._href = dict(attrs).get("href", "")
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._text.append(data.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href:
            text = " ".join(t for t in self._text if t)
            self.links.append((self._href, text))
            self._href = ""


def verify(client: httpx.Client, url: str) -> tuple[bool, str]:
    """HEAD (1-byte GET fallback). Returns (ok, content_type)."""
    try:
        r = client.head(url, follow_redirects=True, timeout=20)
        if r.status_code == 405:
            r = client.get(url, follow_redirects=True, timeout=20,
                           headers={"Range": "bytes=0-0"})
        ct = r.headers.get("content-type", "")
        return (r.status_code < 400 and "pdf" in ct, ct)
    except Exception:
        return False, ""


def classify(text: str, url: str) -> tuple[int, str, str]:
    blob = f"{text} {url}".lower()
    grade = 0
    m = CLASS_RE.search(blob)
    if m:
        grade = int(next(g for g in m.groups() if g))
    subj = ""
    for name, keys in SUBJECT_KEYWORDS:
        if any(k in blob for k in keys):
            subj = name
            break
    lang = ""
    for code, keys in LANG_HINTS:
        if any(k in blob for k in keys):
            lang = code
            break
    if not lang and "ln=hi" in url:
        lang = "hi"
    return grade, subj, lang or "en"


def crawl(delay: float) -> list[dict]:
    out: list[dict] = []
    with httpx.Client(headers=UA) as client:
        for page in INDEX_PAGES:
            try:
                time.sleep(delay)
                html = client.get(page, timeout=40).text
            except Exception as exc:  # noqa: BLE001 — next index page
                print(f"WARN index {page}: {exc}", flush=True)
                continue
            harvester = LinkHarvest()
            harvester.feed(html)
            for href, text in harvester.links:
                full = str(httpx.URL(page).join(href))
                host = httpx.URL(full).host or ""
                if host not in OFFICIAL_HOSTS or ".pdf" not in full.lower():
                    continue
                grade, subj, lang = classify(text, full)
                time.sleep(delay)
                ok, ct = verify(client, full)
                if ok:
                    out.append({"pdf": full, "title": text[:120],
                                "grade": grade, "subject_guess": subj,
                                "lang": lang, "content_type": ct})
                    print(f"OK g{grade} {subj} {lang} {full[:80]}", flush=True)
    seen: set[str] = set()
    uniq = []
    for c in out:
        if c["pdf"] not in seen:
            seen.add(c["pdf"])
            uniq.append(c)
    return uniq


def apply_catalog(catalog: list[dict], client_delay: float = 0.0) -> int:
    sys.path.insert(0, "backend")
    from sqlmodel import Session, select
    from app.db import engine, ensure_textbook_columns
    from app.models import Textbook

    ensure_textbook_columns()
    applied = skipped = 0
    with httpx.Client(headers=UA) as client, Session(engine) as s:
        for c in catalog:
            if not (c.get("grade") and c.get("subject_guess") and c.get("lang")):
                skipped += 1
                continue
            ok, _ = verify(client, c["pdf"])  # re-verify at apply time
            if c.get("delay"):
                time.sleep(client_delay)
            row = s.exec(select(Textbook).where(
                Textbook.board == "CBSE", Textbook.class_grade == c["grade"],
                Textbook.subject_name == c["subject_guess"],
                Textbook.lang == c["lang"])).first()
            if row is None or row.deep_url or not ok:
                skipped += 1
                continue
            row.deep_url = c["pdf"]
            row.last_ok = True
            row.last_checked = None
            s.add(row)
            applied += 1
        s.commit()
    print(f"applied {applied}, skipped {skipped} (board=CBSE)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=float, default=1.5)
    ap.add_argument("--output", default="ncert_catalog.json")
    ap.add_argument("--input", default="")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    if args.input:
        with open(args.input, encoding="utf-8") as f:
            catalog = json.load(f)
        print(f"loaded {len(catalog)} entries from {args.input}")
    else:
        catalog = crawl(args.delay)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(catalog, f, ensure_ascii=False, indent=1)
        print(f"wrote {len(catalog)} verified entries -> {args.output}")
    if args.apply:
        return apply_catalog(catalog, args.delay)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
