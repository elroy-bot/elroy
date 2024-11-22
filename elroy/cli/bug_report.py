import traceback

from ..config.config import ElroyContext
from ..io.cli import CliIO
from ..system_commands import create_bug_report


async def create_bug_report_from_exception_if_confirmed(context: ElroyContext[CliIO], error: Exception) -> None:
    """
    Prompt user to create a bug report from an exception and create it if confirmed.

    Args:
        context: The Elroy context
        error: The exception that triggered this prompt
    """
    if await context.io.prompt_user("An error occurred, would you like to open a pre-filled bug report? (y/n)") == "y":
        create_bug_report(
            context,
            f"Error: {error.__class__.__name__}",
            f"Exception occurred: {str(error)}\n\nTraceback:\n{''.join(traceback.format_tb(error.__traceback__))}",
        )
