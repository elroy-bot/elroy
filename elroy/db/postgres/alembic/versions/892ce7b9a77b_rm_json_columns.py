"""rm json columns

Revision ID: 892ce7b9a77b
Revises: 140daba72332
Create Date: 2024-12-18 08:18:00.389996

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "892ce7b9a77b"
down_revision: Union[str, None] = "140daba72332"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename existing columns to backup
    op.alter_column("contextmessageset", "message_ids", new_column_name="message_ids_bkp")
    op.alter_column("goal", "status_updates", new_column_name="status_updates_bkp")
    op.alter_column("message", "tool_calls", new_column_name="tool_calls_bkp")
    op.alter_column("message", "memory_metadata", new_column_name="memory_metadata_bkp")

    # Create new text columns
    op.add_column("contextmessageset", sa.Column("message_ids", sa.Text(), nullable=True))
    op.add_column("goal", sa.Column("status_updates", sa.Text(), nullable=False, server_default="[]"))
    op.add_column("message", sa.Column("tool_calls", sa.Text(), nullable=True))
    op.add_column("message", sa.Column("memory_metadata", sa.Text(), nullable=True))

    # Transfer data
    op.execute("UPDATE contextmessageset SET message_ids = message_ids_bkp::text")
    op.execute("UPDATE goal SET status_updates = status_updates_bkp::text")
    op.execute("UPDATE message SET tool_calls = tool_calls_bkp::text")
    op.execute("UPDATE message SET memory_metadata = memory_metadata_bkp::text")


def downgrade() -> None:
    # Drop new text columns
    op.drop_column("contextmessageset", "message_ids")
    op.drop_column("goal", "status_updates")
    op.drop_column("message", "tool_calls")
    op.drop_column("message", "memory_metadata")

    # Rename backup columns back to original names
    op.alter_column("contextmessageset", "message_ids_bkp", new_column_name="message_ids")
    op.alter_column("goal", "status_updates_bkp", new_column_name="status_updates")
    op.alter_column("message", "tool_calls_bkp", new_column_name="tool_calls")
    op.alter_column("message", "memory_metadata_bkp", new_column_name="memory_metadata")
