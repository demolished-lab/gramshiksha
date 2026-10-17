"""add offline sync idempotency keys and reset-attempt lockout

Revision ID: a1b2c3d4e5f6
Revises: 9c4d2e7a1b5f
Create Date: 2026-10-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "9c4d2e7a1b5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "offlinesyncevent",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.String(length=80), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "event_id", name="uq_offlinesyncevent_user_event"),
    )
    op.create_index(op.f("ix_offlinesyncevent_user_id"), "offlinesyncevent", ["user_id"], unique=False)

    op.create_table(
        "passwordresetattempt",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_passwordresetattempt_email"), "passwordresetattempt", ["email"], unique=False)
    op.create_index(op.f("ix_passwordresetattempt_created_at"), "passwordresetattempt", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_passwordresetattempt_created_at"), table_name="passwordresetattempt")
    op.drop_index(op.f("ix_passwordresetattempt_email"), table_name="passwordresetattempt")
    op.drop_table("passwordresetattempt")
    op.drop_index(op.f("ix_offlinesyncevent_user_id"), table_name="offlinesyncevent")
    op.drop_table("offlinesyncevent")
