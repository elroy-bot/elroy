"""add_reminder_table

Revision ID: c3f1051dfe01
Revises: ef844ce1225b
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
    # Create unified reminder table
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


def downgrade() -> None:
    # Drop reminder table
    op.drop_table('reminder')
