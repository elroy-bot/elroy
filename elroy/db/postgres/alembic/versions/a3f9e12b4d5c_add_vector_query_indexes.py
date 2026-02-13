"""add vector query indexes

Revision ID: a3f9e12b4d5c
Revises: 2c7579d11c8f
Create Date: 2026-01-20 18:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3f9e12b4d5c"
down_revision: str | None = "2c7579d11c8f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create indexes to speed up vector search queries

    # Index for vectorstorage join on source_type and source_id
    op.create_index(
        "ix_vectorstorage_source_type_source_id",
        "vectorstorage",
        ["source_type", "source_id"],
        unique=False,
    )

    # Index for vectorstorage user filtering
    op.create_index(
        "ix_vectorstorage_user_id",
        "vectorstorage",
        ["user_id"],
        unique=False,
    )

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


def downgrade() -> None:
    # Drop the indexes in reverse order
    op.drop_index("ix_reminder_user_id_is_active", table_name="reminder")
    op.drop_index("ix_memory_user_id_is_active", table_name="memory")
    op.drop_index("ix_vectorstorage_user_id", table_name="vectorstorage")
    op.drop_index("ix_vectorstorage_source_type_source_id", table_name="vectorstorage")
