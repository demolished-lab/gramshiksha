"""add user.role_status (teacher approval workflow)

Revision ID: c4d81a6b90ef
Revises: b1c04a7e2f58
Create Date: 2026-09-29 00:12:45.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision: str = 'c4d81a6b90ef'
down_revision: Union[str, Sequence[str], None] = 'b1c04a7e2f58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the approval flag to `user`.

    server_default='active' matters: every account that already exists
    (seeded staff, real users) is approved by definition, and only
    *self-registered teachers* are written as 'pending' by the application.
    Without the default, this ALTER would fail outright on a table with rows.
    """
    op.add_column(
        'user',
        sa.Column('role_status', sqlmodel.sql.sqltypes.AutoString(),
                  nullable=False, server_default='active'),
    )


def downgrade() -> None:
    """Remove the approval flag (all accounts become active again)."""
    op.drop_column('user', 'role_status')
