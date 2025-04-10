"""rm redundant indicies

Revision ID: a69db7c09d71
Revises: f880962b9187
Create Date: 2025-02-10 09:30:30.345469

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a69db7c09d71"
down_revision: Union[str, None] = "f880962b9187"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# These were all redundant indicies, id is already designated as primary key and thus indexed


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###

    op.drop_index("ix_contextmessageset_id", table_name="contextmessageset")
    op.drop_index("ix_goal_id", table_name="goal")
    op.drop_index("ix_memory_id", table_name="memory")
    op.drop_index("ix_message_id", table_name="message")
    op.drop_index("ix_user_id", table_name="user")
    op.drop_index("ix_userpreference_id", table_name="userpreference")
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_index("ix_userpreference_id", "userpreference", ["id"], unique=False)
    op.create_index("ix_user_id", "user", ["id"], unique=False)
    op.create_index("ix_message_id", "message", ["id"], unique=False)
    op.create_index("ix_memory_id", "memory", ["id"], unique=False)
    op.create_index("ix_goal_id", "goal", ["id"], unique=False)
    op.create_index("ix_contextmessageset_id", "contextmessageset", ["id"], unique=False)
    # ### end Alembic commands ###
