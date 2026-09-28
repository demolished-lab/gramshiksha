"""add batch table (teacher-owned class groups)

Revision ID: b1c04a7e2f58
Revises: f77e214dfd32
Create Date: 2026-09-28 23:41:12.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision: str = 'b1c04a7e2f58'
down_revision: Union[str, Sequence[str], None] = 'f77e214dfd32'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the table `progress.py`'s POST /progress/batches writes to.

    The router imported a Batch model that never existed, which is part of
    why that router was never mounted. Additive only — no existing table is
    touched, so this is safe against the production database.
    """
    op.create_table(
        'batch',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('teacher_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['teacher_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_batch_teacher_id'), 'batch', ['teacher_id'], unique=False)


def downgrade() -> None:
    """Drop the batch table."""
    op.drop_index(op.f('ix_batch_teacher_id'), table_name='batch')
    op.drop_table('batch')
