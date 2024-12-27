import logging
import os
import subprocess

from ..config.ctx import ElroyContext
from ..utils.ops import experimental


@experimental
def make_coding_edit(ctx: ElroyContext, working_dir: str, instruction: str, file_name: str) -> str:
    """Instructs a delegated coding LLM to make an edit to code. As context is being passed transferred to the assistant, care must be taken to ensure the assistant has all necessary context.

    Args:
        context: The ElroyContext instance
        working_dir: Directory to work in
        instruction: The edit instruction. This should be exhaustive, and include any raw data needed to make the edit. It should also include any instructions based on memory or feedback as relevant.
        file_name: File to edit

    Returns:
        The git diff output as a string
    """
    from aider.coders import Coder
    from aider.io import InputOutput
    from aider.models import Model

    logging.info(f"Instructions to aider: {instruction}")

    # Store current dir
    original_dir = os.getcwd()

    try:
        # Change to working dir
        os.chdir(working_dir)

        coder = Coder.create(
            main_model=Model(ctx.chat_model.name),
            fnames=[file_name],
            io=InputOutput(yes=True),
            auto_commits=False,
        )
        coder.run(instruction)

        # Get git diff
        result = subprocess.run(["git", "diff"], capture_output=True, text=True, check=True)
        return f"Coding change complete, the following diff was generated:\n{result.stdout}"

    finally:
        # Restore original dir
        os.chdir(original_dir)
