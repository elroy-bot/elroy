"""add user authentication fields

Revision ID: add_user_auth_fields
Revises: b360a1f1b06e
Create Date: 2025-08-03 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlmodel.sql.sqltypes import AutoString

# revision identifiers, used by Alembic.
revision: str = "add_user_auth_fields"
down_revision: Union[str, None] = "b360a1f1b06e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add email and password_hash columns
    op.add_column("user", sa.Column("email", AutoString(), nullable=True))
    op.add_column("user", sa.Column("password_hash", AutoString(), nullable=True))

    # Create unique index on email
    op.create_index("ix_user_email", "user", ["email"], unique=True)


def downgrade() -> None:
    # Drop the columns
    op.drop_index("ix_user_email", "user")
    op.drop_column("user", "password_hash")
    op.drop_column("user", "email")
