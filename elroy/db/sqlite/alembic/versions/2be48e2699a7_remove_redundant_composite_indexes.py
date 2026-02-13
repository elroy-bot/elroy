"""remove redundant composite indexes

Revision ID: 2be48e2699a7
Revises: b7e2a34c1f8d
Create Date: 2026-01-22 10:00:09.073020

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2be48e2699a7"
down_revision: str | None = "b7e2a34c1f8d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop redundant composite indexes
    # These were added in b7e2a34c1f8d but are no longer needed
    op.drop_index("ix_memory_id_user_id", table_name="memory")
    op.drop_index("ix_memory_user_id_is_active", table_name="memory")
    op.drop_index("ix_reminder_id_user_id", table_name="reminder")
    op.drop_index("ix_reminder_user_id_is_active", table_name="reminder")


def downgrade() -> None:
    # Re-create the indexes if rolling back
    op.create_index(
        "ix_reminder_user_id_is_active",
        "reminder",
        ["user_id", "is_active"],
        unique=False,
    )
    op.create_index(
        "ix_reminder_id_user_id",
        "reminder",
        ["id", "user_id"],
        unique=False,
    )
    op.create_index(
        "ix_memory_user_id_is_active",
        "memory",
        ["user_id", "is_active"],
        unique=False,
    )
    op.create_index(
        "ix_memory_id_user_id",
        "memory",
        ["id", "user_id"],
        unique=False,
    )
