"""add_user_id_to_vector_storage

Revision ID: a2780f233908
Revises: 18b5805a011b
Create Date: 2025-07-27 12:40:26.608550

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a2780f233908"
down_revision: Union[str, None] = "18b5805a011b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add nullable user_id column to vectorstorage table
    op.add_column("vectorstorage", sa.Column("user_id", sa.Integer(), nullable=True))

    # Backfill user_id for each source type
    connection = op.get_bind()

    # Update VectorStorage records for Memory table
    connection.execute(
        sa.text(
            """
        UPDATE vectorstorage
        SET user_id = (
            SELECT m.user_id
            FROM memory m
            WHERE m.id = vectorstorage.source_id
        )
        WHERE vectorstorage.source_type = 'Memory'
    """
        )
    )

    # Update VectorStorage records for DocumentExcerpt table
    connection.execute(
        sa.text(
            """
        UPDATE vectorstorage
        SET user_id = (
            SELECT de.user_id
            FROM documentexcerpt de
            WHERE de.id = vectorstorage.source_id
        )
        WHERE vectorstorage.source_type = 'DocumentExcerpt'
    """
        )
    )

    # Update VectorStorage records for Goal table
    connection.execute(
        sa.text(
            """
        UPDATE vectorstorage
        SET user_id = (
            SELECT g.user_id
            FROM goal g
            WHERE g.id = vectorstorage.source_id
        )
        WHERE vectorstorage.source_type = 'Goal'
    """
        )
    )

    # Update VectorStorage records for ContextMessageSetWithMessages
    connection.execute(
        sa.text(
            """
        UPDATE vectorstorage
        SET user_id = (
            SELECT cms.user_id
            FROM contextmessageset cms
            WHERE cms.id = vectorstorage.source_id
        )
        WHERE vectorstorage.source_type = 'ContextMessageSetWithMessages'
    """
        )
    )

    # Delete orphaned vectorstorage records where user_id is NULL
    connection.execute(sa.text("DELETE FROM vectorstorage WHERE user_id IS NULL"))

    # Set user_id column to not null
    op.alter_column("vectorstorage", "user_id", nullable=False)


def downgrade() -> None:
    # Remove user_id column from vectorstorage table
    op.drop_column("vectorstorage", "user_id")
