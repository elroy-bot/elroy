import asyncio

from elroy.cli.context import get_user_logged_in_message
from elroy.messaging.context import context_refresh


def test_context_refresh(george_context):
    asyncio.run(context_refresh(george_context))


def test_user_login_msg(onboarded_context):
    get_user_logged_in_message(onboarded_context)
    # TODO: more specific test that takes context into account (with test clock)
