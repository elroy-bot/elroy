import asyncio

from elroy.messaging.context import context_refresh


def test_context_refresh(george_context):
    asyncio.run(context_refresh(george_context))
