from elroy.messaging.context import compress_context_messages, count_tokens
from elroy.repository.message import get_context_messages


def test_consolidate_context(george_context):

    # create a very long context to test consolidation
    new_messages = compress_context_messages(george_context, get_context_messages(george_context) * 10)

    assert count_tokens(george_context.config.chat_model.model, new_messages) < george_context.config.context_refresh_token_target * 1.5
