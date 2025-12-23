"""add vector query indexes

Revision ID: b7e2a34c1f8d
Revises: 899126f0e215
Create Date: 2026-01-20 18:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7e2a34c1f8d"
down_revision: Union[str, None] = "899126f0e215"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create indexes to speed up vector search queries

    # Note: We cannot create indexes on vectorstorage because it's a virtual table
    # (using sqlite-vec's vec0). Virtual tables have their own internal indexing.
    # We can only index the regular tables that join with it.

    # Index for memory queries (user_id + is_active filter)
    op.create_index(
        "ix_memory_user_id_is_active",
        "memory",
        ["user_id", "is_active"],
        unique=False,
    )

    # Index for reminder queries (user_id + is_active filter)
    op.create_index(
        "ix_reminder_user_id_is_active",
        "reminder",
        ["user_id", "is_active"],
        unique=False,
    )

    # Index for memory table to speed up joins
    op.create_index(
        "ix_memory_id_user_id",
        "memory",
        ["id", "user_id"],
        unique=False,
    )

    # Index for reminder table to speed up joins
    op.create_index(
        "ix_reminder_id_user_id",
        "reminder",
        ["id", "user_id"],
        unique=False,
    )


def downgrade() -> None:
    # Drop the indexes in reverse order
    op.drop_index("ix_reminder_id_user_id", table_name="reminder")
    op.drop_index("ix_memory_id_user_id", table_name="memory")
    op.drop_index("ix_reminder_user_id_is_active", table_name="reminder")
    op.drop_index("ix_memory_user_id_is_active", table_name="memory")
