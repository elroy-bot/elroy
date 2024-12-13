from datetime import datetime

from lorem_text import lorem
from pytz import UTC

from elroy.config.constants import SYSTEM_INSTRUCTION_LABEL
from elroy.messaging.context import compress_context_messages, count_tokens
from elroy.repository.data_models import ASSISTANT, SYSTEM, USER, ContextMessage


def test_compress_context_messages(george_context):
    # create a very long context to test consolidation
    system_message = ContextMessage(role=SYSTEM, content=f"{SYSTEM_INSTRUCTION_LABEL}\nSystem message", chat_model=None)
    original_messages = [system_message]

    for i in range(50):
        original_messages += [
            ContextMessage(role=USER, content=f"{i}\n" + lorem.paragraph(), chat_model=None, created_at=datetime.now(UTC)),
            ContextMessage(
                role=ASSISTANT,
                content=f"{i}\n" + lorem.paragraph(),
                chat_model=george_context.config.chat_model,
                created_at=datetime.now(UTC),
            ),
        ]

    compressed_messages = compress_context_messages(george_context, original_messages)

    # Test token count
    assert (
        count_tokens(george_context.config.chat_model.name, compressed_messages) < george_context.config.context_refresh_token_target * 1.5
    )

    # Test message ordering
    assert compressed_messages[0] == system_message, "System message should be kept"

    # Test that relative ordering of non-system messages is preserved
    for idx, msg in enumerate(compressed_messages[1:]):
        if idx < len(compressed_messages) - 1:
            msg_idx = int(msg.content.split("\n")[0])  # type: ignore
            next_msg_idx = int(compressed_messages[idx + 1].content.split("\n")[0])  # type: ignore

            assert msg_idx <= next_msg_idx, "Message relative order should be preserved"
