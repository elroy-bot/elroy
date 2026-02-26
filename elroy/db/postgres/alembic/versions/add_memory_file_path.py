"""add file_path to Memory and make text nullable

Revision ID: c3d4e5f6a7b8
Revises: f2a3b4c5d6e7
Create Date: 2026-02-25 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "f2a3b4c5d6e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add file_path column
    op.add_column("memory", sa.Column("file_path", sa.String(), nullable=True))

    # Make text nullable
    op.alter_column("memory", "text", existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    op.alter_column("memory", "text", existing_type=sa.String(), nullable=False)
    op.drop_column("memory", "file_path")
