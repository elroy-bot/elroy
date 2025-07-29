"""consolidate_reminders_into_unified_table

Revision ID: cc91a5b0fd61
Revises: 803e60219bef
Create Date: 2025-07-29 09:45:52.184586

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cc91a5b0fd61'
down_revision: Union[str, None] = 'a2780f233908'
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
    result = connection.execute(sa.text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'timedreminder'
        );
    """))
    
    if result.scalar():
        connection.execute(sa.text("""
            INSERT INTO reminder (id, created_at, updated_at, user_id, name, text, trigger_datetime, is_active, is_recurring)
            SELECT id, created_at, updated_at, user_id, name, text, trigger_datetime, is_active, false
            FROM timedreminder
        """))

    # Migrate data from contextualreminder table if it exists
    result = connection.execute(sa.text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'contextualreminder'
        );
    """))
    
    if result.scalar():
        connection.execute(sa.text("""
            INSERT INTO reminder (id, created_at, updated_at, user_id, name, text, reminder_context, is_active, is_recurring)
            SELECT id, created_at, updated_at, user_id, name, text, reminder_context, is_active, is_recurring
            FROM contextualreminder
        """))

    # Drop old tables if they exist
    op.execute("DROP TABLE IF EXISTS timedreminder")
    op.execute("DROP TABLE IF EXISTS contextualreminder")


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
        SELECT id, created_at, updated_at, user_id, name, text, reminder_context, is_active, COALESCE(is_recurring, false)
        FROM reminder
        WHERE reminder_context IS NOT NULL
    """))

    # Drop unified table
    op.drop_table('reminder')
