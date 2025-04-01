from lorem_text import lorem

from elroy.core.constants import ASSISTANT, SYSTEM, SYSTEM_INSTRUCTION_LABEL, USER
from elroy.core.ctx import ElroyContext
from elroy.llm.utils import count_tokens
from elroy.repository.context_messages.data_models import ContextMessage
from elroy.repository.context_messages.transforms import compress_context_messages


def test_compress_context_messages(george_ctx: ElroyContext):
    # create a very long context to test consolidation
    system_message = ContextMessage(
        role=SYSTEM,
        content=f"{SYSTEM_INSTRUCTION_LABEL}\nSystem message",
        chat_model=None,
    )
    original_messages = [system_message]

    for i in range(50):
        original_messages += [
            ContextMessage(
                role=USER,
                content=f"{i}\n" + lorem.paragraph(),
                chat_model=None,
            ),
            ContextMessage(
                role=ASSISTANT,
                content=f"{i}\n" + lorem.paragraph(),
                chat_model=george_ctx.chat_model.name,
            ),
        ]

    compressed_messages = compress_context_messages(
        george_ctx.chat_model.name,
        george_ctx.context_refresh_target_tokens,
        george_ctx.max_in_context_message_age,
        original_messages,
    )

    # Test token count
    assert count_tokens(george_ctx.chat_model.name, compressed_messages) < george_ctx.context_refresh_target_tokens * 1.5

    # Test message ordering
    assert compressed_messages[0] == system_message, "System message should be kept"

    # Test that relative ordering of non-system messages is preserved
    for idx, msg in enumerate(compressed_messages[1:]):
        if idx < len(compressed_messages) - 1:
            msg_idx = int(msg.content.split("\n")[0])  # type: ignore
            next_msg_idx = int(compressed_messages[idx + 1].content.split("\n")[0])  # type: ignore

            assert msg_idx <= next_msg_idx, "Message relative order should be preserved"
