"""centralize vectors

Revision ID: 140daba72332
Revises: 71ffabe55f21
Create Date: 2024-12-17 13:39:05.264792

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "140daba72332"
down_revision: Union[str, None] = "71ffabe55f21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the vector extension if it doesn't exist
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create the vectorstorage table with native vector support
    op.create_table(
        "vectorstorage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("embedding_data", Vector(dim=1536), nullable=False),
        sa.Column("embedding_text_md5", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Backfill data from memory table
    op.execute(
        text(
            """
        INSERT INTO vectorstorage (created_at, updated_at, source_type, source_id, embedding_data, embedding_text_md5)
        SELECT created_at, updated_at, 'Memory', id, embedding, embedding_text_md5
        FROM memory 
        WHERE embedding IS NOT NULL AND embedding_text_md5 IS NOT NULL
        """
        )
    )

    # Backfill data from goal table
    op.execute(
        text(
            """
        INSERT INTO vectorstorage (created_at, updated_at, source_type, source_id, embedding_data, embedding_text_md5)
        SELECT created_at, updated_at, 'Goal', id, embedding, embedding_text_md5
        FROM goal
        WHERE embedding IS NOT NULL AND embedding_text_md5 IS NOT NULL
        """
        )
    )

    # Note: We're not dropping the old columns yet - that will be done in a separate migration
    # after we verify the data migration worked correctly


def downgrade() -> None:
    # Drop the vectorstorage table
    op.drop_table("vectorstorage")

    # Note: The vector extension is left installed as other databases might use it
