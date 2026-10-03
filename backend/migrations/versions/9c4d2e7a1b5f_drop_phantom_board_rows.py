"""drop phantom board rows (HSC 1-10, SSC 11-12 duplicates)

Revision ID: 9c4d2e7a1b5f
Revises: 8f2a6c1d9e4b
Create Date: 2026-10-03 10:40:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '9c4d2e7a1b5f'
down_revision: Union[str, Sequence[str], None] = '8f2a6c1d9e4b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Seed Urdu titles follow "{en} — جماعت {grade} (بال بھارتی)" exactly —
# portal-crawled rows never look like that, so the relabel below (and its
# reversal) can target the pattern without touching crawler-ingested rows.
_UR_SEED_LIKE = "% جماعت % (بال بھارتی)"


def upgrade() -> None:
    """Remove board/grade combinations that cannot exist.

    The seeder used to emit every board for every grade, so two phantom
    combos accumulated: Maharashtra HSC for classes 1-10 (HSC starts at 11)
    and Maharashtra SSC for 11-12 (SSC ends at 10). Every one of those rows
    lacks a deep link, and all but 22 duplicate a correctly-labeled row with
    a healthy PDF. The 22 survivors are Urdu-medium 11-12 books with no HSC
    counterpart — real Balbharati content — so they are relabeled, not
    dropped. After this, availability stops offering HSC 1-10 and SSC 11-12
    entirely instead of showing dead shelves.
    """
    # 1. HSC 1-10: all 114 verified exact duplicates of deep SSC rows.
    op.execute(
        "DELETE FROM textbook "
        "WHERE board = 'Maharashtra HSC' AND class_grade <= 10")
    # 2. SSC 11-12 duplicates of HSC rows.
    op.execute(
        "DELETE FROM textbook WHERE board = 'Maharashtra SSC' "
        "AND class_grade >= 11 AND EXISTS ("
        "SELECT 1 FROM textbook AS r WHERE r.board = 'Maharashtra HSC' "
        "AND r.class_grade = textbook.class_grade "
        "AND r.subject_name = textbook.subject_name AND r.lang = textbook.lang)")
    # 3. SSC 11-12 Urdu rows with no HSC counterpart -> relabel to HSC.
    op.execute(
        "UPDATE textbook SET board = 'Maharashtra HSC' "
        "WHERE board = 'Maharashtra SSC' AND class_grade >= 11")


def downgrade() -> None:
    """Reverse the relabel; deleted duplicate rows are not restored.

    The 158 deleted rows were exact duplicates (same grade/subject/lang) of
    surviving rows that carry the verified deep PDFs, so nothing readable is
    lost by their absence — re-running the seeder regenerates placeholders.
    The 22 relabeled Urdu rows are identifiable by the seed's exact title
    pattern and move back to SSC.
    """
    op.execute(
        "UPDATE textbook SET board = 'Maharashtra SSC' "
        "WHERE board = 'Maharashtra HSC' AND class_grade >= 11 "
        "AND lang = 'ur' AND title LIKE '" + _UR_SEED_LIKE + "'")
