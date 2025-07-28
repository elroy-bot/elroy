from tests.utils import MockCliIO

from elroy.core.constants import ASSISTANT, SYSTEM, USER
from elroy.core.ctx import ElroyContext
from elroy.db.db_models import Memory
from elroy.repository.context_messages.data_models import (
    ContextMessage,
    RecalledMemoryMetadata,
)
from elroy.repository.context_messages.operations import (
    add_context_messages,
    eject_irrelevant_memories,
)
from elroy.repository.context_messages.queries import get_context_messages
from elroy.repository.memories.queries import is_memory_message


def test_assistant_memory_in_context(io: MockCliIO, ctx: ElroyContext):
    add_context_messages(
        ctx,
        [
            ContextMessage(
                chat_model=ctx.chat_model.name,
                role=SYSTEM,
                content="The user likes to go bowling",
                memory_metadata=[RecalledMemoryMetadata(memory_type=Memory.__name__, id=1, name="User's bowling preferences")],
            ),
            ContextMessage(
                chat_model=ctx.chat_model.name,
                role=SYSTEM,
                content="The user has been to China",
                memory_metadata=[RecalledMemoryMetadata(memory_type=Memory.__name__, id=2, name="Trip to China")],
            ),
            ContextMessage(
                chat_model=ctx.chat_model.name,
                role=USER,
                content="I'm thinking about going bowling today!",
            ),
            ContextMessage(
                chat_model=ctx.chat_model.name,
                role=ASSISTANT,
                content="That's great, I think that's a great idea",
            ),
        ],
    )

    eject_irrelevant_memories(ctx)
    memory_messages = [m for m in get_context_messages(ctx) if is_memory_message(m)]

    assert len(memory_messages) == 1

    assert memory_messages[0].content == "The user likes to go bowling"
