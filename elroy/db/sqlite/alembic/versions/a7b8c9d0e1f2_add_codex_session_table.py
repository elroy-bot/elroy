"""add codex session table

Revision ID: a7b8c9d0e1f2
Revises: f2a3b4c5d6e7
Create Date: 2026-05-07 19:15:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlmodel.sql.sqltypes import AutoString

# revision identifiers, used by Alembic.
revision: str = "a7b8c9d0e1f2"
down_revision: str | None = "f2a3b4c5d6e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "codexsession",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("thread_id", AutoString(), nullable=False),
        sa.Column("repo_path", AutoString(), nullable=False),
        sa.Column("latest_prompt", sa.Text(), nullable=False),
        sa.Column("latest_summary", sa.Text(), nullable=True),
        sa.Column("latest_agent_message", sa.Text(), nullable=True),
        sa.Column("status", AutoString(), nullable=False),
        sa.Column("command_count", sa.Integer(), nullable=False),
        sa.Column("commands_json", sa.Text(), nullable=False),
        sa.Column("touched_paths_json", sa.Text(), nullable=False),
        sa.Column("dirty_paths_before_json", sa.Text(), nullable=False),
        sa.Column("dirty_paths_after_json", sa.Text(), nullable=False),
        sa.Column("session_file_path", AutoString(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "thread_id"),
    )


def downgrade() -> None:
    op.drop_table("codexsession")
