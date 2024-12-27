import asyncio
import traceback

from ..config.ctx import ElroyContext
from ..io.cli import CliIO
from ..tools.developer import create_bug_report


def create_bug_report_from_exception_if_confirmed(
    ctx: ElroyContext, error: Exception, error_explanation: str = "An error occured."
) -> None:
    """
    Prompt user to create a bug report from an exception and create it if confirmed.

    Args:
        context: The Elroy context
        error: The exception that triggered this prompt
    """
    io = ctx.io
    if not isinstance(io, CliIO):
        return

    if asyncio.run(get_confirm(io, f"{error_explanation} Would you like to create a bug report? (y/n)")):
        create_bug_report(
            ctx,
            f"Error: {error.__class__.__name__}",
            f"Exception occurred: {str(error)}\n\nTraceback:\n{''.join(traceback.format_tb(error.__traceback__))}",
        )
    raise error


async def get_confirm(io: CliIO, prompt: str) -> bool:
    """Prompt the user to confirm an action"""
    response = await io.prompt_user(prompt)
    return response.lower().startswith("y")
