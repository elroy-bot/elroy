from elroy.memory.system_context import (consolidate_context, count_tokens,
                                         format_context_messages)
from elroy.store.message import get_context_messages


def test_consolidate_context(session, context_refresh_token_target, george_user_id):

    # create a very long context to test consolidation
    new_messages = consolidate_context(context_refresh_token_target, get_context_messages(session, george_user_id) * 10)

    assert count_tokens(format_context_messages("George", new_messages)) < context_refresh_token_target * 1.5
