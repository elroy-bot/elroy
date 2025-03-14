import re

from elroy.cli.chat import process_and_deliver_msg
from elroy.core.constants import USER
from elroy.core.ctx import ElroyContext
from elroy.repository.goals.queries import get_active_goal_names

from .utils import MockCliIO


def test_create_and_mark_goal_complete(io: MockCliIO, ctx: ElroyContext):
    io.add_user_responses("Test Goal", "", "", "", "", "")

    process_and_deliver_msg(
        io,
        USER,
        ctx,
        "/create_goal Test Goal",
    )

    assert "Test Goal" in get_active_goal_names(ctx)

    assert "Test Goal" in io.get_sys_messages()

    io.add_user_responses("Test Goal", "The test was completed!")

    process_and_deliver_msg(io, USER, ctx, "/mark_goal_completed Test Goal")

    assert "Test Goal" not in get_active_goal_names(ctx)

    assert re.search(r"Test Goal.*completed", io.get_sys_messages()) is not None


def test_invalid_update(io: MockCliIO, ctx: ElroyContext):
    io.add_user_responses("Nonexistent goal", "Foo")
    process_and_deliver_msg(
        io,
        USER,
        ctx,
        "/mark_goal_completed",
    )

    response = io.get_sys_messages()
    assert re.search(r"Error.*.*not exist", response) is not None


def test_invalid_cmd(io: MockCliIO, ctx: ElroyContext):
    process_and_deliver_msg(
        io,
        USER,
        ctx,
        "/foo",
    )
    response = io.get_sys_messages()
    assert re.search(r"Invalid.*foo.*help", response) is not None
