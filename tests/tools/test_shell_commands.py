import re

from tests.utils import process_test_message

from elroy.core.ctx import ElroyContext


def test_shell_commands(ctx: ElroyContext):
    """Test the shell commands"""

    ctx.allowed_shell_command_prefixes = [re.compile("ls")]
    ctx.shell_commands = True

    assert "ls -l" in process_test_message(ctx, "Run shell command: ls -l")


def test_unapproved_shell_comand(ctx: ElroyContext):
    ctx.allowed_shell_command_prefixes = [re.compile("ls")]
    ctx.shell_commands = True

    assert "Error invoking tool run_shell_command" in process_test_message(ctx, "Run shell command: echo foo")


def test_shell_commands_disabled(ctx: ElroyContext):
    """Test the shell commands"""

    ctx.shell_commands = False

    for schema in ctx.tool_registry.get_schemas():
        assert schema["function"]["name"] != "run_shell_command"
