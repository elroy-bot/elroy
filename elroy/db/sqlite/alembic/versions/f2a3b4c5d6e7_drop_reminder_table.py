"""drop reminder table

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-03-31 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlmodel.sql.sqltypes import AutoString

# revision identifiers, used by Alembic.
revision: str = "f2a3b4c5d6e7"
down_revision: str | None = "e1f2a3b4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS reminder")


def downgrade() -> None:
    op.create_table(
        "reminder",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", AutoString(), nullable=False),
        sa.Column("text", AutoString(), nullable=False),
        sa.Column("trigger_datetime", sa.DateTime(), nullable=True),
        sa.Column("reminder_context", AutoString(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("status", AutoString(), nullable=False),
        sa.Column("closing_comment", AutoString(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", "is_active", "trigger_datetime", "status", "reminder_context"),
    )
