"""add background_ingest_last_run to UserPreference

Revision ID: a1b2c3d4e5f6
Revises: 2be48e2699a7
Create Date: 2026-02-11 17:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "2be48e2699a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add background_ingest_last_run column as nullable
    op.add_column(
        "userpreference",
        sa.Column("background_ingest_last_run", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    # Remove background_ingest_last_run column
    op.drop_column("userpreference", "background_ingest_last_run")
