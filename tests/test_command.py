import re

import pytest

from elroy.cli.chat import process_and_deliver_msg
from elroy.config.constants import USER
from elroy.system_commands import get_active_goal_names


@pytest.mark.asyncio
async def test_create_and_mark_goal_complete(elroy_context):
    elroy_context.io.add_user_responses("Test Goal", "", "", "", "", "")

    await process_and_deliver_msg(USER, elroy_context, "/create_goal Test Goal")

    assert "Test Goal" in get_active_goal_names(elroy_context)

    assert "Test Goal" in elroy_context.io.get_sys_messages()[-1]

    elroy_context.io.add_user_responses("Test Goal", "The test was completed!")

    await process_and_deliver_msg(USER, elroy_context, "/mark_goal_completed Test Goal")

    assert "Test Goal" not in get_active_goal_names(elroy_context)

    assert re.search(r"Test Goal.*completed", elroy_context.io.get_sys_messages()[-1]) is not None


@pytest.mark.asyncio
async def test_print_config(elroy_context):

    await process_and_deliver_msg(USER, elroy_context, "/print_elroy_config")
    response = elroy_context.io.get_sys_messages()[-1]
    assert response and "context_refresh_token_target" in response  # just picking a random key


@pytest.mark.asyncio
async def test_invalid_update(elroy_context):
    elroy_context.io.add_user_responses("Nonexistent goal", "Foo")
    await process_and_deliver_msg(USER, elroy_context, "/mark_goal_completed")

    response = elroy_context.io.get_sys_messages()[-1]
    assert re.search(r"Error.*Nonexistent goal.*not found", response) is not None


@pytest.mark.asyncio
async def test_invalid_cmd(elroy_context):
    await process_and_deliver_msg(USER, elroy_context, "/foo")
    response = elroy_context.io.get_sys_messages()[-1]
    assert re.search(r"Unknown.*foo", response) is not None
