"""add reminder fields to agenda item

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-03-31 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlmodel.sql.sqltypes import AutoString

# revision identifiers, used by Alembic.
revision: str = "e1f2a3b4c5d6"
down_revision: str | None = "d0e1f2a3b4c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("agendaitem", sa.Column("trigger_datetime", sa.DateTime(), nullable=True))
    op.add_column("agendaitem", sa.Column("reminder_context", AutoString(), nullable=True))
    op.add_column("agendaitem", sa.Column("status", AutoString(), nullable=False, server_default="created"))
    op.add_column("agendaitem", sa.Column("closing_comment", AutoString(), nullable=True))
    op.execute("DELETE FROM reminder")


def downgrade() -> None:
    op.drop_column("agendaitem", "closing_comment")
    op.drop_column("agendaitem", "status")
    op.drop_column("agendaitem", "reminder_context")
    op.drop_column("agendaitem", "trigger_datetime")
