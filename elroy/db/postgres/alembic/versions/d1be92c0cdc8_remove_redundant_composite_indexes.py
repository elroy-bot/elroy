"""remove redundant composite indexes

Revision ID: d1be92c0cdc8
Revises: a3f9e12b4d5c
Create Date: 2026-01-22 10:00:37.323150

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1be92c0cdc8"
down_revision: Union[str, None] = "a3f9e12b4d5c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop redundant composite indexes
    # These were added in e8f85ea5a3ff but are no longer needed
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
