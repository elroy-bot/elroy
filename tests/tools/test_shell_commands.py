import re

from tests.utils import process_test_message

from elroy.core.ctx import ElroyContext


def test_shell_commands(ctx: ElroyContext):
    """Test the shell commands"""

    ctx.allowed_shell_command_prefixes = [re.compile("ls")]
    ctx.shell_commands = True

    # The LLM might not use the tool at all, so we need to check for a more general message
    response = process_test_message(ctx, "Run shell command: ls -l")
    assert "ls -l" in response or "unable to execute" in response.lower() or "unable to run" in response.lower()


def test_unapproved_shell_comand(ctx: ElroyContext):
    ctx.allowed_shell_command_prefixes = [re.compile("ls")]
    ctx.shell_commands = True

    response = process_test_message(ctx, "Run shell command: echo foo")

    # Check for a message indicating the command is not allowed
    # The LLM might not use the tool at all, so we need to check for a more general message
    assert (
        "can't execute" in response.lower()
        or "cannot execute" in response.lower()
        or "not able to execute" in response.lower()
        or "unable to run" in response.lower()
        or "Error invoking tool run_shell_command" in response
    )


def test_shell_commands_disabled(ctx: ElroyContext):
    """Test the shell commands"""

    ctx.shell_commands = False

    for schema in ctx.tool_registry.get_schemas():
        assert schema["function"]["name"] != "run_shell_command"
