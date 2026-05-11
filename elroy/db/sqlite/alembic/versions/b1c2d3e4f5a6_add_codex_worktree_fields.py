"""add codex worktree fields

Revision ID: b1c2d3e4f5a6
Revises: a7b8c9d0e1f2
Create Date: 2026-05-11 12:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlmodel.sql.sqltypes import AutoString

# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: str | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("codexsession", sa.Column("worktree_path", AutoString(), nullable=True))
    op.add_column("codexsession", sa.Column("session_branch", AutoString(), nullable=True))
    op.add_column("codexsession", sa.Column("target_branch", AutoString(), nullable=True))


def downgrade() -> None:
    op.drop_column("codexsession", "target_branch")
    op.drop_column("codexsession", "session_branch")
    op.drop_column("codexsession", "worktree_path")
