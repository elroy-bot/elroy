import re

import pytest

from elroy.cli.chat import process_and_deliver_msg
from elroy.config.constants import USER
from elroy.system_commands import get_active_goal_names


@pytest.mark.asyncio
async def test_create_and_mark_goal_complete(ctx):
    ctx.io.add_user_responses("Test Goal", "", "", "", "", "")

    await process_and_deliver_msg(USER, ctx, "/create_goal Test Goal")

    assert "Test Goal" in get_active_goal_names(ctx)

    assert "Test Goal" in ctx.io.get_sys_messages()[-1]

    ctx.io.add_user_responses("Test Goal", "The test was completed!")

    await process_and_deliver_msg(USER, ctx, "/mark_goal_completed Test Goal")

    assert "Test Goal" not in get_active_goal_names(ctx)

    assert re.search(r"Test Goal.*completed", ctx.io.get_sys_messages()[-1]) is not None


@pytest.mark.asyncio
async def test_print_config(ctx):
    await process_and_deliver_msg(USER, ctx, "/print_elroy_config")
    response = ctx.io.get_sys_messages()[-1]
    assert response and "l2_memory_relevance_distance_threshold" in response  # just picking a random key


@pytest.mark.asyncio
async def test_invalid_update(ctx):
    ctx.io.add_user_responses("Nonexistent goal", "Foo")
    await process_and_deliver_msg(USER, ctx, "/mark_goal_completed")

    response = ctx.io.get_sys_messages()[-1]
    assert re.search(r"Error.*Nonexistent goal.*not found", response) is not None


@pytest.mark.asyncio
async def test_invalid_cmd(ctx):
    await process_and_deliver_msg(USER, ctx, "/foo")
    response = ctx.io.get_sys_messages()[-1]
    assert re.search(r"Unknown.*foo", response) is not None
