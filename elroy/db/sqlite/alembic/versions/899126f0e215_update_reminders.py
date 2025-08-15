"""update reminders

Revision ID: 899126f0e215
Revises: 1c74c74a43e2
Create Date: 2025-08-15 12:02:55.852145

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlmodel.sql.sqltypes import AutoString

# revision identifiers, used by Alembic.
revision: str = "899126f0e215"
down_revision: Union[str, None] = "1c74c74a43e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite doesn't support ALTER CONSTRAINT, so we need to recreate the table

    # Add new columns first
    op.add_column("reminder", sa.Column("status", AutoString(), nullable=True))  # Make nullable initially
    op.add_column("reminder", sa.Column("closing_comment", AutoString(), nullable=True))

    # Backfill status column
    op.execute("UPDATE reminder SET status = 'created' WHERE status IS NULL")

    # Create a new table with the updated constraint
    op.create_table(
        "reminder_new",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", AutoString(), nullable=False),
        sa.Column("text", AutoString(), nullable=False),
        sa.Column("trigger_datetime", sa.DateTime(), nullable=True),
        sa.Column("reminder_context", AutoString(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("status", AutoString(), nullable=False),
        sa.Column("closing_comment", AutoString(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", "is_active", "trigger_datetime", "status", "reminder_context"),
    )

    # Copy data to new table
    op.execute(
        """
        INSERT INTO reminder_new (id, created_at, updated_at, user_id, name, text, 
                                 trigger_datetime, reminder_context, is_active, status, closing_comment)
        SELECT id, created_at, updated_at, user_id, name, text, 
               trigger_datetime, reminder_context, is_active, status, closing_comment
        FROM reminder
    """
    )

    # Drop old table and rename new one
    op.drop_table("reminder")
    op.rename_table("reminder_new", "reminder")


def downgrade() -> None:
    # Recreate the original table structure
    op.create_table(
        "reminder_old",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", AutoString(), nullable=False),
        sa.Column("text", AutoString(), nullable=False),
        sa.Column("trigger_datetime", sa.DateTime(), nullable=True),
        sa.Column("reminder_context", AutoString(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", "is_active"),
    )

    # Copy data back (excluding new columns)
    op.execute(
        """
        INSERT INTO reminder_old (id, created_at, updated_at, user_id, name, text, 
                                 trigger_datetime, reminder_context, is_active)
        SELECT id, created_at, updated_at, user_id, name, text, 
               trigger_datetime, reminder_context, is_active
        FROM reminder
    """
    )

    # Drop current table and rename old one
    op.drop_table("reminder")
    op.rename_table("reminder_old", "reminder")
