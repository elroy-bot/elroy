#!/usr/bin/env python3
import os
import subprocess
from typing import List

from aider.coders import Coder
from aider.io import InputOutput
from aider.models import Model
from semantic_version import Version

from elroy import __version__
from elroy.api import Elroy

WORKING_DIR = os.path.expanduser("~/development/elroy")


def augment_with_memory(elroy: Elroy, instruction: str) -> str:
    return elroy.message(
        f"""The following is instructions for a task.
                  If there are any specific memories that would be relevant to this task,
                  update the text of the instructions to incorporate it.
                  Be sure to retain any information that is in the original instruction.

                  The following is the original instruction:
                  {instruction}
                  """
    )


def make_edit(elroy: Elroy, instruction: str, rw_files: List[str], ro_files: List[str] = []) -> None:
    memory_augmented_instructions = augment_with_memory(elroy, instruction)

    Coder.create(
        main_model=Model("o1-preview"),
        fnames=rw_files,
        read_only_fnames=ro_files,
        io=InputOutput(yes=True),
        auto_commits=False,
    ).run(memory_augmented_instructions)


def sync_help_and_readme(elroy: Elroy):
    # Get git repo root

    # Get commits since last release
    help_output = subprocess.run(["elroy", "help"], capture_output=True, text=True).stdout.strip()

    make_edit(
        elroy,
        f"""The following below text is the output of elroy --help.
              Make any edits to README.md that would make the document more complete and accurate:

              {help_output}""",
        ["README.md"],
    )


# aider --file elroy/cli/main.py elroy/defaults.yml elroy/config/ctx.py --no-auto-commit -m '
def sync_configuration_and_cli_ops(elroy: Elroy):
    make_edit(
        elroy,
        instruction=f"""
Review main.py and elroy/defaults.yml. The configuration options in defaults.yml correspond to the command line options in main.py.
Make sure the comments in defaults.yml are in sync with the command line options in main.py.
The headings should be the same, ie the YAML should have comments corresponding to the name of the rich_help_panel of the main.py options
These headings should also be present in ctx.py for the ElroyContext constructor.
    """,
        rw_files=["elroy/cli/main.py", "elroy/defaults.yml"],
    )


def update_readme(elroy: Elroy):
    make_edit(
        elroy,
        instruction="""Review main.py, system_commands.py and README.md. Make any edits that would make the document more complete.
Pay particular attention to:
- Ensuring all assistant tools are documented under the "## Available assistant and CLI Commands" section of the README. See system_commands.py for the list of available assistant/CLI tools.
- Ensure the README accurately describes which models are supported by Elroy.

Do NOT remove any links or gifs.""",
        rw_files=["README.md", "elroy/cli/main.py", "elroy/system_commands.py"],
    )


def update_changelog(elroy: Elroy):
    commits = os.popen(f'git log {__version__}..HEAD --pretty=format:"- %s"').read()

    instruction = f"""
    Update CHANGELOG.md to add version $NEXT_VERSION. Here are the commits since the last release:

    {commits}

    Please:
    1. Add a new entry at the top of the changelog for version $NEXT_VERSION dated $TODAY
    2. Group the commits into appropriate sections (Added, Fixed, Improved, Infrastructure, etc.) based on their content
    3. Clean up and standardize the commit messages to be more readable
    4. Maintain the existing changelog format

    Do NOT remove any existing entries.

    Note that not all housekeeping updates need to be mentioned. Only those changes that a maintainer or user would be interested in should be included.

    """

    make_edit(elroy, instruction, ["CHANGELOG.md"])


if __name__ == "__main__":
    elroy = Elroy(user_token="docs-prep")

    repo_root = os.popen("git rev-parse --show-toplevel").read().strip()
    os.chdir(repo_root)

    sync_help_and_readme(elroy)

    next_tag = Version(__version__).next_patch()

    sync_help_and_readme(elroy)
    sync_configuration_and_cli_ops(elroy)
    update_readme(elroy)
    update_changelog(elroy)

    exit
    # Wait for user to confirm changes
    input("Press Enter to commit changes")

    os.system("git add .")
    os.system(f"git commit -m 'Release {next_tag}'")
    os.system("git push")
    os.system(f"gh pr create --fill")
    input("Press enter to merge pr")
    os.system("gh pr merge")
    os.system(f"git tag {next_tag}")
    os.system(f"git push origin {next_tag}")
    print("Please provide feedback on the changes made in this release")
    feedback = input()
    elroy.remember(feedback, name=f"Feedback for release {next_tag}")
