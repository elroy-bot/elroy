import traceback
from concurrent.futures import ThreadPoolExecutor

from ..core.ctx import ElroyContext
from ..io.cli import CliIO
from ..tools.developer import create_bug_report


def create_bug_report_from_exception_if_confirmed(
    io: CliIO, ctx: ElroyContext, error: Exception, error_explanation: str = "An error occured."
) -> None:
    """
    Prompt user to create a bug report from an exception and create it if confirmed.

    Args:
        error: The exception that triggered this prompt
    """
    if get_confirm(ctx.thread_pool, io, f"{error_explanation} Would you like to create a bug report? (y/n)"):
        create_bug_report(
            ctx,
            f"Error: {error.__class__.__name__}",
            f"Exception occurred: {str(error)}\n\nTraceback:\n{''.join(traceback.format_tb(error.__traceback__))}",
        )
    raise error


def get_confirm(thread_pool: ThreadPoolExecutor, io: CliIO, prompt: str) -> bool:
    """Prompt the user to confirm an action"""
    try:
        response = io.prompt_user(thread_pool, 0, prompt)
        return response.lower().startswith("y")
    except EOFError:
        return False
