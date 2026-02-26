"""add file_path to Memory and make text nullable

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-25 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add file_path column
    op.add_column("memory", sa.Column("file_path", sa.String(), nullable=True))

    # Make text nullable by recreating the column with nullable=True
    # SQLite doesn't support ALTER COLUMN, so we use batch_alter_table
    with op.batch_alter_table("memory") as batch_op:
        batch_op.alter_column("text", existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("memory") as batch_op:
        batch_op.alter_column("text", existing_type=sa.String(), nullable=False)
    op.drop_column("memory", "file_path")
