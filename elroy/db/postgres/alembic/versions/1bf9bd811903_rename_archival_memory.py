"""rename archival memory

Revision ID: 1bf9bd811903
Revises: bc853b0f6e47
Create Date: 2024-10-19 16:33:52.165364

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "1bf9bd811903"
down_revision: str | None = "bc853b0f6e47"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
