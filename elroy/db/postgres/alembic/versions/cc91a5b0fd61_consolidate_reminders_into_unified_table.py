"""add_reminder_table

Revision ID: cc91a5b0fd61
Revises: a2780f233908
Create Date: 2025-07-29 09:45:52.184586

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cc91a5b0fd61"
down_revision: str | None = "a2780f233908"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create unified reminder table
    op.create_table(
        "reminder",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("text", sa.String(), nullable=False),
        sa.Column("trigger_datetime", sa.DateTime(), nullable=True),
        sa.Column("reminder_context", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", "is_active"),
    )


def downgrade() -> None:
    # Drop reminder table
    op.drop_table("reminder")
