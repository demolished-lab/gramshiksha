"""add textbook.part_label (multi-part books: भाग-1 / Part 2)

Revision ID: e5b8c2d7a1f6
Revises: d9e2f4a1b7c3
Create Date: 2026-10-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision: str = 'e5b8c2d7a1f6'
down_revision: Union[str, Sequence[str], None] = 'd9e2f4a1b7c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Give multi-part subjects one row per part.

    The crawler maps "परिसर अभ्यास भाग-१/२" onto separate rows; the column
    labels which part a row is ('Part 1', 'Part 2') and stays '' for every
    whole book. server_default='' matters: without it this ALTER fails on a
    textbook table that already has rows.

    Idempotent by inspection: production is a *stamped* database, and its
    boot path also runs the ensure_textbook_columns shim — if that shim ever
    added part_label before this revision replayed there, replaying it
    unguarded would crash startup with a duplicate-column error.
    """
    conn = op.get_bind()
    existing = {c["name"] for c in sa.inspect(conn).get_columns("textbook")}
    if "part_label" in existing:
        return
    op.add_column(
        'textbook',
        sa.Column('part_label', sqlmodel.sql.sqltypes.AutoString(),
                  nullable=False, server_default=''),
    )


def downgrade() -> None:
    """Drop the part label (part books collapse back onto their seed row)."""
    op.drop_column('textbook', 'part_label')
