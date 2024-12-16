import os
import subprocess

from ..config.config import ElroyContext
from ..utils.ops import experimental


@experimental
def make_coding_edit(context: ElroyContext, working_dir: str, instruction: str, file_name: str) -> str:
    """Make a coding edit in the specified directory and return the git diff.

    Args:
        context: The ElroyContext instance
        working_dir: Directory to work in
        instruction: The edit instruction
        file_name: File to edit

    Returns:
        The git diff output as a string
    """
    from aider.coders import Coder
    from aider.io import InputOutput
    from aider.models import Model

    # Store current dir
    original_dir = os.getcwd()

    try:
        # Change to working dir
        os.chdir(working_dir)

        coder = Coder.create(
            main_model=Model(context.config.chat_model.name),
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
