"""add user.referred_by (referral virality loop)

Revision ID: d9e2f4a1b7c3
Revises: c4d81a6b90ef
Create Date: 2026-09-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9e2f4a1b7c3'
down_revision: Union[str, Sequence[str], None] = 'c4d81a6b90ef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Who invited this account (nullable FK to user.id).

    Nullable with no default: every existing account simply has no referrer.
    The public referral code is derived ("GS%06d" % id), so no code column
    is needed and nothing backfills.

    Batch mode: SQLite cannot ALTER a table to add a column+constraint, so
    Alembic rebuilds the table (copy-and-move). The same path runs on
    Postgres — one table, a handful of rows at deploy time — so both
    dialects end with the identical schema and the drift guard stays green.
    """
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(sa.Column("referred_by", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_user_referred_by_user", "user",
                                    ["referred_by"], ["id"])
    op.create_index("ix_user_referred_by", "user", ["referred_by"])


def downgrade() -> None:
    """Drop the referral link (codes derived from ids stop resolving)."""
    op.drop_index("ix_user_referred_by", table_name="user")
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_constraint("fk_user_referred_by_user", type_="foreignkey")
        batch_op.drop_column("referred_by")
