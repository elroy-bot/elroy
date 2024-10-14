from elroy.memory.system_context import context_refresh


def test_context_refresh(george_context, context_refresh_token_target):
    context_refresh(george_context, context_refresh_token_target)
