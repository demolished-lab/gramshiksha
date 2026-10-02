"""add bookrequest table (book finder queue)

Revision ID: b3d4a5257fff
Revises: e5b8c2d7a1f6
Create Date: 2026-10-03 03:31:13.938503

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision: str = 'b3d4a5257fff'
down_revision: Union[str, Sequence[str], None] = 'e5b8c2d7a1f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the queue POST /library/locate writes to.

    One row per unfound search; the keep-warm loop re-scans pendings and
    flips them to 'found' (+ notifies the requester) once an official PDF
    lands. query is indexed because dedupe ("is this exact ask already
    queued?") and the position count both filter on it.
    """
    op.create_table('bookrequest',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('query', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('class_grade', sa.Integer(), nullable=True),
    sa.Column('board', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('lang', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('textbook_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('found_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['textbook_id'], ['textbook.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_bookrequest_class_grade'), 'bookrequest', ['class_grade'], unique=False)
    op.create_index(op.f('ix_bookrequest_query'), 'bookrequest', ['query'], unique=False)
    op.create_index(op.f('ix_bookrequest_user_id'), 'bookrequest', ['user_id'], unique=False)


def downgrade() -> None:
    """Drop the queue — pending asks are lost, fulfilled ones live on as rows."""
    op.drop_index(op.f('ix_bookrequest_user_id'), table_name='bookrequest')
    op.drop_index(op.f('ix_bookrequest_query'), table_name='bookrequest')
    op.drop_index(op.f('ix_bookrequest_class_grade'), table_name='bookrequest')
    op.drop_table('bookrequest')
