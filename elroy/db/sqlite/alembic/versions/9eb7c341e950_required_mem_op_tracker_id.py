"""required mem op tracker id

Revision ID: 9eb7c341e950
Revises: c8c496bfdfc6
Create Date: 2025-04-07 09:04:29.370278

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9eb7c341e950"
down_revision: str | None = "c8c496bfdfc6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create a temporary table to store the existing data
    op.execute(
        """
        CREATE TABLE memoryoperationtracker_temp (
            id INTEGER PRIMARY KEY NOT NULL,
            user_id INTEGER NOT NULL,
            memories_since_consolidation INTEGER NOT NULL DEFAULT 0,
            messages_since_memory INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL
        )
    """
    )

    # Copy data from the original table to the temporary table
    op.execute(
        """
        INSERT INTO memoryoperationtracker_temp
        SELECT id, user_id, memories_since_consolidation, messages_since_memory, created_at, updated_at
        FROM memoryoperationtracker
    """
    )

    # Drop the original table
    op.drop_table("memoryoperationtracker")

    # Create the new table with the non-nullable id
    op.create_table(
        "memoryoperationtracker",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("memories_since_consolidation", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("messages_since_memory", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )

    # Copy data back from the temporary table to the new table
    op.execute(
        """
        INSERT INTO memoryoperationtracker (id, user_id, memories_since_consolidation, messages_since_memory, created_at, updated_at)
        SELECT id, user_id, memories_since_consolidation, messages_since_memory, created_at, updated_at
        FROM memoryoperationtracker_temp
    """
    )

    # Drop the temporary table
    op.drop_table("memoryoperationtracker_temp")


def downgrade() -> None:
    # Create a temporary table with nullable id
    op.execute(
        """
        CREATE TABLE memoryoperationtracker_temp (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            memories_since_consolidation INTEGER NOT NULL DEFAULT 0,
            messages_since_memory INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL
        )
    """
    )

    # Copy data from the original table to the temporary table
    op.execute(
        """
        INSERT INTO memoryoperationtracker_temp
        SELECT id, user_id, memories_since_consolidation, messages_since_memory, created_at, updated_at
        FROM memoryoperationtracker
    """
    )

    # Drop the original table
    op.drop_table("memoryoperationtracker")

    # Create the new table with nullable id
    op.create_table(
        "memoryoperationtracker",
        sa.Column("id", sa.Integer(), nullable=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("memories_since_consolidation", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("messages_since_memory", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )

    # Copy data back from the temporary table to the new table
    op.execute(
        """
        INSERT INTO memoryoperationtracker (id, user_id, memories_since_consolidation, messages_since_memory, created_at, updated_at)
        SELECT id, user_id, memories_since_consolidation, messages_since_memory, created_at, updated_at
        FROM memoryoperationtracker_temp
    """
    )

    # Drop the temporary table
    op.drop_table("memoryoperationtracker_temp")
