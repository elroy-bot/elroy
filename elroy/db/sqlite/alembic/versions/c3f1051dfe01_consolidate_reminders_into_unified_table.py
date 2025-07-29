"""consolidate_reminders_into_unified_table

Revision ID: c3f1051dfe01
Revises: 599fac28c92f
Create Date: 2025-07-29 09:46:33.184229

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3f1051dfe01'
down_revision: Union[str, None] = 'ef844ce1225b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create new unified reminder table
    op.create_table(
        'reminder',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('text', sa.String(), nullable=False),
        sa.Column('trigger_datetime', sa.DateTime(), nullable=True),
        sa.Column('reminder_context', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('is_recurring', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Migrate data from timedreminder table if it exists
    connection = op.get_bind()
    
    # Check if timedreminder table exists and migrate data
    try:
        result = connection.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name='timedreminder'"))
        if result.fetchone():
            connection.execute(sa.text("""
                INSERT INTO reminder (id, created_at, updated_at, user_id, name, text, trigger_datetime, is_active, is_recurring)
                SELECT id, created_at, updated_at, user_id, name, text, trigger_datetime, is_active, 0
                FROM timedreminder
            """))
    except Exception:
        pass  # Table doesn't exist, skip migration

    # Check if contextualreminder table exists and migrate data
    try:
        result = connection.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name='contextualreminder'"))
        if result.fetchone():
            connection.execute(sa.text("""
                INSERT INTO reminder (id, created_at, updated_at, user_id, name, text, reminder_context, is_active, is_recurring)
                SELECT id, created_at, updated_at, user_id, name, text, reminder_context, is_active, is_recurring
                FROM contextualreminder
            """))
    except Exception:
        pass  # Table doesn't exist, skip migration

    # Drop old tables if they exist
    try:
        op.drop_table('timedreminder')
    except Exception:
        pass
    
    try:
        op.drop_table('contextualreminder')
    except Exception:
        pass


def downgrade() -> None:
    # Recreate old tables
    op.create_table(
        'timedreminder',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('text', sa.String(), nullable=False),
        sa.Column('trigger_datetime', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'contextualreminder',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('text', sa.String(), nullable=False),
        sa.Column('reminder_context', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('is_recurring', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Migrate data back from unified table
    connection = op.get_bind()
    
    # Migrate timed reminders
    connection.execute(sa.text("""
        INSERT INTO timedreminder (id, created_at, updated_at, user_id, name, text, trigger_datetime, is_active)
        SELECT id, created_at, updated_at, user_id, name, text, trigger_datetime, is_active
        FROM reminder
        WHERE trigger_datetime IS NOT NULL
    """))

    # Migrate contextual reminders
    connection.execute(sa.text("""
        INSERT INTO contextualreminder (id, created_at, updated_at, user_id, name, text, reminder_context, is_active, is_recurring)
        SELECT id, created_at, updated_at, user_id, name, text, reminder_context, is_active, COALESCE(is_recurring, 0)
        FROM reminder
        WHERE reminder_context IS NOT NULL
    """))

    # Drop unified table
    op.drop_table('reminder')
