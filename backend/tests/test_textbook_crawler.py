"""Textbook crawler upgrades: parts, dynamic cataloging, CDN covers.

Contract under test:
- parse_part: Devanagari "भाग-१" and English "Part 2" both normalize; ordinary
  titles stay partless; part_key orders partless < Part 1 < Part 2 so apply is
  deterministic.
- guess_subject/subject_fallback: unknown subjects fall back to the CLEANED
  title (class prefix and medium stripped) instead of being dropped, and
  edition markers collapse duplicate editions onto one subject while keeping
  genuinely different books distinct.
- apply_catalog (private board, so the shared suite never sees the rows):
  fills empty rows, never overwrites a deep_url, splits multi-part subjects
  onto separate rows (part 1 claims the partless stand-in), creates rows for
  books we don't seed, skips re-listed duplicates, and is idempotent on re-run.
- _textbook_out: part_label rides the API; covers rewrite to Cloudinary's
  transform CDN when configured and stay on the origin otherwise.

Literal paths in endpoint calls because the route-coverage canary parses
string literals. Private board rows are removed by the cleanup fixture —
test_production asserts /textbooks/coverage lists exactly three real boards.
"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db import engine
from app.main import app
from app.models import Textbook
from scripts.crawl_ebalbharati import (
    apply_catalog, guess_subject, norm_title, parse_part, part_key,
    subject_fallback,
)

BOARD = "Crawler Test Board"


@pytest.fixture(name="client")
def client_fixture():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _db_ready():
    """Pure/apply tests never start the TestClient, so initialize the schema
    the same way app startup does — otherwise SELECTs hit a missing table."""
    from app.db import create_db_and_tables

    create_db_and_tables()
    yield


@pytest.fixture(autouse=True)
def _cleanup_private_board():
    yield
    with Session(engine) as s:
        for row in s.exec(select(Textbook).where(Textbook.board == BOARD)).all():
            s.delete(row)
        s.commit()


def _entry(title: str, *, grade: int = 3, lang: str = "mr", subject: str = "",
           pdf_id: str = "999") -> dict:
    return {"title": title, "grade": grade, "lang": lang,
            "subject_guess": subject,
            "pdf": f"https://ebooks.ebalbharati.in/pdfs/{pdf_id}.pdf",
            "cover": f"https://books.ebalbharati.in/BookCovers/{pdf_id}.jpg"}


class TestPartParsing:
    def test_devanagari_part(self):
        assert parse_part("५ वी परिसर अभ्यास भाग-१ मराठी") == "Part 1"

    def test_devanagari_part_two(self):
        assert parse_part("५ वी परिसर अभ्यास भाग-२ हिंदी") == "Part 2"

    def test_english_part(self):
        assert parse_part("History Part 2") == "Part 2"

    def test_whole_book_is_not_a_part(self):
        assert parse_part("८ वी गणित मराठी") == ""

    def test_part_word_without_number_is_not_a_part(self):
        assert parse_part("Participant Handbook") == ""

    def test_part_key_orders_partless_first(self):
        titles = ["X Part 2", "X", "Y भाग-1"]
        assert [part_key({"title": t}) for t in titles] == [2, 0, 1]


class TestSubjectFallback:
    def test_unknown_title_becomes_subject(self):
        assert guess_subject("Class 8 Weird Book", "en") == "Weird Book"

    def test_class_prefix_stripped(self):
        assert subject_fallback("८ वी विचित्र पुस्तक मराठी") == "विचित्र पुस्तक"

    def test_sanskrit_editions_collapse_to_one_subject(self):
        a = guess_subject("संस्कृतम् आमोद:(संपूर्ण)", "mr")
        b = guess_subject("संस्कृतम् आनन्द:(संयुक्त)", "mr")
        assert a == b == "Sanskrit"

    def test_distinct_books_stay_distinct(self):
        assert (subject_fallback("पाली प्रवेशिका")
                != subject_fallback("पाली प्रवेश"))

    def test_known_subjects_keep_canonical_names(self):
        assert guess_subject("८ वी सामान्य विज्ञान मराठी", "mr") == "Science"
        assert guess_subject("Mathematics Part 1", "en") == "Mathematics"

    def test_norm_title_ignores_medium_and_whitespace(self):
        assert norm_title("गणित  मराठी") == norm_title("गणित मराठी")


class TestApplyCatalog:
    def _run(self, entries, board=BOARD):
        return apply_catalog(entries, board)

    def test_creates_row_for_unseeded_official_book(self, capsys):
        self._run([_entry("८ वी विचित्र पुस्तक", subject="विचित्र पुस्तक",
                          pdf_id="701")])
        with Session(engine) as s:
            row = s.exec(select(Textbook).where(
                Textbook.board == BOARD, Textbook.class_grade == 3,
                Textbook.subject_name == "विचित्र पुस्तक")).first()
            assert row is not None
            assert row.deep_url.endswith("/701.pdf")
            assert row.last_ok is True and row.last_checked is None
            assert row.source_url == "https://books.ebalbharati.in"
        assert "created 1" in capsys.readouterr().out

    def test_fills_existing_empty_row_never_overwrites(self, capsys):
        with Session(engine) as s:
            s.add(Textbook(board=BOARD, class_grade=3, subject_name="Science",
                           lang="mr", title="Seed Science",
                           source_url="https://example.org",
                           publisher="Official"))
            s.commit()
        entry = _entry("विज्ञान पुस्तक", subject="Science", pdf_id="702")
        self._run([entry])
        # identical re-crawl: PDF-id anchor → no touch, no duplicate row
        self._run([entry])
        with Session(engine) as s:
            rows = s.exec(select(Textbook).where(
                Textbook.board == BOARD, Textbook.subject_name == "Science")).all()
            assert len(rows) == 1
            assert rows[0].deep_url.endswith("/702.pdf")
            assert rows[0].title == "Seed Science"  # fill never rewrites title
        out = capsys.readouterr().out
        assert "applied 1, created 0" in out.splitlines()[0]
        assert "applied 0, created 0, skipped 1" in out.splitlines()[1]

    def test_parts_split_onto_separate_rows(self, capsys):
        with Session(engine) as s:
            s.add(Textbook(board=BOARD, class_grade=3,
                           subject_name="Environmental Studies", lang="mr",
                           title="EVS seed", source_url="https://example.org",
                           publisher="Official"))
            s.commit()
        self._run([
            _entry("परिसर अभ्यास भाग-२ मराठी",
                   subject="Environmental Studies", pdf_id="712"),
            _entry("परिसर अभ्यास भाग-१ मराठी",
                   subject="Environmental Studies", pdf_id="711"),
        ])
        with Session(engine) as s:
            rows = s.exec(select(Textbook).where(
                Textbook.board == BOARD,
                Textbook.subject_name == "Environmental Studies"
            ).order_by(Textbook.part_label)).all()
            assert [r.part_label for r in rows] == ["Part 1", "Part 2"]
            by_part = {r.part_label: r for r in rows}
            # sorted apply: Part 1 claimed the seed row before Part 2 created
            assert by_part["Part 1"].title == "EVS seed"
            assert by_part["Part 1"].deep_url.endswith("/711.pdf")
            assert by_part["Part 2"].deep_url.endswith("/712.pdf")
        assert "created 1" in capsys.readouterr().out

    def test_distinct_same_subject_books_both_kept(self):
        self._run([
            _entry("पाली प्रवेशिका", subject="Pali", pdf_id="721"),
            _entry("पाली प्रवेश", subject="Pali", pdf_id="722"),
        ])
        with Session(engine) as s:
            rows = s.exec(select(Textbook).where(
                Textbook.board == BOARD, Textbook.subject_name == "Pali")).all()
            assert len(rows) == 2

    def test_exact_duplicate_titles_collapse(self, capsys):
        self._run([
            _entry("संस्कृतम् आमोद:(संपूर्ण)", subject="Sanskrit", pdf_id="731"),
            _entry("संस्कृतम् आमोद:(संपूर्ण)", subject="Sanskrit", pdf_id="732"),
        ])
        with Session(engine) as s:
            rows = s.exec(select(Textbook).where(
                Textbook.board == BOARD, Textbook.subject_name == "Sanskrit")).all()
            assert len(rows) == 1
            assert rows[0].deep_url.endswith("/731.pdf")

    def test_second_run_is_idempotent(self, capsys):
        entries = [_entry("नवीन विषय पुस्तक", subject="नवीन विषय", pdf_id="741")]
        self._run(entries)
        capsys.readouterr()
        self._run(entries)
        out = capsys.readouterr().out
        assert "applied 0, created 0" in out
        with Session(engine) as s:
            rows = s.exec(select(Textbook).where(Textbook.board == BOARD)).all()
            assert len(rows) == 1


class TestTextbookOut:
    def _row(self, **kw) -> Textbook:
        base = dict(board="B", class_grade=1, subject_name="S", lang="mr",
                    title="T", source_url="https://example.org")
        base.update(kw)
        return Textbook(**base)

    def test_part_label_and_plain_cover_by_default(self):
        from app.routers.catalog import _textbook_out
        out = _textbook_out(self._row(cover_url="https://x.example/c.jpg"))
        assert out["part_label"] is None
        assert out["cover_url"] == "https://x.example/c.jpg"

    def test_part_label_rides_the_api(self):
        from app.routers.catalog import _textbook_out
        out = _textbook_out(self._row(part_label="Part 2"))
        assert out["part_label"] == "Part 2"

    def test_cover_rewrites_to_cloudinary_when_configured(self, monkeypatch):
        from app.config import settings
        from app.routers.catalog import _textbook_out
        monkeypatch.setattr(settings, "cloudinary_cloud_name", "testcloud")
        out = _textbook_out(self._row(cover_url="https://x.example/c.jpg"))
        assert out["cover_url"].startswith(
            "https://res.cloudinary.com/testcloud/image/fetch/f_auto,q_auto,w_360/")
        assert "x.example%2Fc.jpg" in out["cover_url"]

    def test_cover_falls_back_when_cloud_name_missing(self, monkeypatch):
        from app.config import settings
        from app.routers.catalog import _textbook_out
        monkeypatch.setattr(settings, "cloudinary_cloud_name", "")
        out = _textbook_out(self._row(cover_url="https://x.example/c.jpg"))
        assert out["cover_url"] == "https://x.example/c.jpg"


class TestTextbooksEndpointPartLabel:
    def test_textbooks_list_exposes_part_label(self, client):
        with Session(engine) as s:
            s.add(Textbook(board=BOARD, class_grade=3, subject_name="Parts",
                           lang="mr", part_label="Part 1", title="P1",
                           source_url="https://example.org",
                           publisher="Official"))
            s.commit()
        r = client.get("/api/textbooks?class_grade=3&board=Crawler Test Board")
        assert r.status_code == 200
        (book,) = r.json()
        assert book["part_label"] == "Part 1"
