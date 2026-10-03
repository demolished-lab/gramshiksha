"""add stream columns (Classes 11-12 Science/Commerce/Arts/Vocational)

Revision ID: 8f2a6c1d9e4b
Revises: 656bef4a6ace
Create Date: 2026-10-03 08:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f2a6c1d9e4b'
down_revision: Union[str, Sequence[str], None] = '656bef4a6ace'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Self-contained copy of app.streams' mapping (migrations must not import
# app code that later edits could change the meaning of).
# (mirrors app.streams, including its deliberate gaps: Mathematics and
# Computer Science are multi-stream, so they stay common.)
_SCIENCE = ("physics", "biology", "chemistry", "science")
_COMMERCE = ("economics", "पुस्तपालन व लेखाकर्म", "वाणिज्य संघटन व व्यवस्थापन",
             "चिटणिसाची कार्यपध्दती", "सहकार")
_ARTS = ("history", "civics", "geography", "तत्वज्ञान", "तर्कशास्त्र",
         "मानसशास्त्र", "समाजशास्त्र", "शिक्षणशास्त्र", "संरक्षणशास्त्र",
         "भूशास्त्र")
_VOCATIONAL = ("गृहव्यवस्थापन", "बाल विकास", "वस्त्रशास्त्र",
               "ग्रंथालय व माहितीशास्त्र")

_STREAM_TABLES = ("textbook", "subject", "material", "bookrequest",
                  "readingpick", "doubt")


def _case_sql(column: str = "subject_name") -> str:
    def _in(names):
        return ", ".join(f"'{n}'" for n in names)
    return f"""CASE
        WHEN lower({column}) IN ({_in(_SCIENCE)}) THEN 'science'
        WHEN lower({column}) IN ({_in(_COMMERCE)}) THEN 'commerce'
        WHEN lower({column}) IN ({_in(_ARTS)}) THEN 'arts'
        WHEN lower({column}) IN ({_in(_VOCATIONAL)}) THEN 'vocational'
        ELSE '' END"""


def upgrade() -> None:
    """Stream categorization for Classes 11-12, everywhere at once.

    `stream` is "" (common to all streams) by default — shared subjects
    (languages, Mathematics, EVS) stay visible under every stream, and
    classes 1-10 keep the flat subject list. Backfill classifies the rows
    streams actually exist for (grade >= 11); doubts/reading picks queued
    before this revision stay common, which is what they were.
    """
    for table in _STREAM_TABLES:
        op.add_column(table, sa.Column(
            "stream", sa.String(), server_default="", nullable=False))
        op.create_index(op.f(f"ix_{table}_stream"), table, ["stream"],
                        unique=False)
    op.execute(
        "UPDATE textbook SET stream = " + _case_sql("subject_name")
        + " WHERE class_grade >= 11")
    op.execute(
        "UPDATE subject SET stream = " + _case_sql("name_en")
        + " WHERE class_grade >= 11")


def downgrade() -> None:
    """Drop stream categorization (filters fall back to flat subjects)."""
    for table in _STREAM_TABLES:
        op.drop_index(op.f(f"ix_{table}_stream"), table_name=table)
        op.drop_column(table, "stream")
