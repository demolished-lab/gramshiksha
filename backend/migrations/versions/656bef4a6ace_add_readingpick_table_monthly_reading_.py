"""add readingpick table (monthly reading list)

Revision ID: 656bef4a6ace
Revises: b3d4a5257fff
Create Date: 2026-10-03 04:39:28.709515

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision: str = '656bef4a6ace'
down_revision: Union[str, Sequence[str], None] = 'b3d4a5257fff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the Monthly Reading List table.

    GET /library/reading is public (book club: every student sees every
    teacher's pick), so month/title/teacher are the indexes the list sorts
    and de-duplicates on; textbook_id points at the catalog row when the
    pick is already readable in-app.
    """
    op.create_table('readingpick',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('teacher_id', sa.Integer(), nullable=False),
    sa.Column('month', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('title', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('author', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('note', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('lang', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('subject_name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('class_grade', sa.Integer(), nullable=True),
    sa.Column('board', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('textbook_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['teacher_id'], ['user.id'], ),
    sa.ForeignKeyConstraint(['textbook_id'], ['textbook.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_readingpick_class_grade'), 'readingpick', ['class_grade'], unique=False)
    op.create_index(op.f('ix_readingpick_month'), 'readingpick', ['month'], unique=False)
    op.create_index(op.f('ix_readingpick_teacher_id'), 'readingpick', ['teacher_id'], unique=False)
    op.create_index(op.f('ix_readingpick_title'), 'readingpick', ['title'], unique=False)


def downgrade() -> None:
    """Drop the reading list (picks are re-creatable by their teachers)."""
    op.drop_index(op.f('ix_readingpick_title'), table_name='readingpick')
    op.drop_index(op.f('ix_readingpick_teacher_id'), table_name='readingpick')
    op.drop_index(op.f('ix_readingpick_month'), table_name='readingpick')
    op.drop_index(op.f('ix_readingpick_class_grade'), table_name='readingpick')
    op.drop_table('readingpick')
