import asyncio
import traceback

from ..config.config import ElroyContext
from ..io.cli import CliIO
from ..system_commands import create_bug_report


def create_bug_report_from_exception_if_confirmed(
    context: ElroyContext[CliIO], error: Exception, error_explanation: str = "An error occured."
) -> None:
    """
    Prompt user to create a bug report from an exception and create it if confirmed.

    Args:
        context: The Elroy context
        error: The exception that triggered this prompt
    """

    if asyncio.run(get_confirm(context.io, f"{error_explanation} Would you like to create a bug report? (y/n)")):
        create_bug_report(
            context,
            f"Error: {error.__class__.__name__}",
            f"Exception occurred: {str(error)}\n\nTraceback:\n{''.join(traceback.format_tb(error.__traceback__))}",
        )


async def get_confirm(io: CliIO, prompt: str) -> bool:
    """Prompt the user to confirm an action"""
    response = await io.prompt_user(prompt)
    return response.lower().startswith("y")
