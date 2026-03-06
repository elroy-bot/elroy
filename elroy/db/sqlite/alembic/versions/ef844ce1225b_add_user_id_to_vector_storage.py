"""add_user_id_to_vector_storage

Revision ID: ef844ce1225b
Revises: 9eb7c341e950
Create Date: 2025-07-27 12:40:54.080721

"""

import logging
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "ef844ce1225b"
down_revision: str | None = "9eb7c341e950"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Previously migrated vectorstorage to include user_id (sqlite-vec virtual table).
    # sqlite-vec is no longer supported; vectors are stored in ChromaDB.
    # This migration is a no-op for new installs; existing vec0 tables are read-only
    # by the ChromaDB migration utility and then abandoned.
    logging.debug("Skipping vectorstorage user_id migration (sqlite-vec no longer supported)")


def downgrade() -> None:
    pass
