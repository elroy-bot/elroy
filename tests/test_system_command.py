from elroy.tools.system_commands import (get_active_goal_names,
                                         invoke_system_command)


def test_create_and_mark_goal_complete(elroy_context):
    invoke_system_command(elroy_context, "create_goal Test Goal")
    assert "Test Goal" in get_active_goal_names(elroy_context)

    invoke_system_command(elroy_context, "mark_goal_completed Test Goal")

    assert "Test Goal" not in get_active_goal_names(elroy_context)
