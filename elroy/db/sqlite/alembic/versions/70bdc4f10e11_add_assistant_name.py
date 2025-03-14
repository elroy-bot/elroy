"""add assistant name

Revision ID: 70bdc4f10e11
Revises: 955beece0126
Create Date: 2024-12-26 21:52:42.434422

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlmodel.sql.sqltypes import AutoString

# revision identifiers, used by Alembic.
revision: str = "70bdc4f10e11"
down_revision: Union[str, None] = "955beece0126"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("userpreference", sa.Column("assistant_name", AutoString(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("userpreference", "assistant_name")
    # ### end Alembic commands ###
