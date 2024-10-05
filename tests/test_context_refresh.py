from elroy.memory.system_context import context_refresh


def test_context_refresh(session, context_refresh_token_target, george_user_id):
    context_refresh(session, context_refresh_token_target, george_user_id)
