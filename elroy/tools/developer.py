import os
import platform
import pty
import subprocess
import sys
import termios
import time
import tty
import urllib.parse
import webbrowser
from dataclasses import asdict
from datetime import datetime
from pprint import pformat
from typing import Optional

import scrubadub
from toolz import pipe
from toolz.curried import filter

from .. import __version__
from ..config.config import ElroyContext
from ..config.constants import BUG_REPORT_LOG_LINES, REPO_ISSUES_URL
from ..llm import client
from ..utils.ops import experimental
from ..utils.utils import obscure_sensitive_info


@experimental
def tail_elroy_logs(context: ElroyContext, lines: int = 10) -> str:
    """
    Returns the last `lines` of the Elroy logs.
    Useful for troubleshooting in cases where errors occur (especially with tool calling).

    Args:
        context (ElroyContext): context obj
        lines (int, optional): Number of lines to return. Defaults to 10.

    Returns:
        str: The last `lines` of the Elroy logs
    """
    with open(context.config.log_file_path, "r") as f:
        return "".join(f.readlines()[-lines:])


def print_elroy_config(context: ElroyContext) -> str:
    """
    Prints the current Elroy configuration.
    Useful for troubleshooting and verifying the current configuration.

    Args:
        context (ElroyContext): context obj

    Returns:
        str: The current Elroy configuration
    """
    return str(context.config)


def create_bug_report(
    context: ElroyContext,
    title: str,
    description: Optional[str],
) -> None:
    """
    Generate a bug report and open it as a GitHub issue.

    Args:
        context: The Elroy context
        title: The title for the bug report
        description: Detailed description of the issue
    """
    # Start building the report
    report = [
        f"# Bug Report: {title}",
        f"\nCreated: {datetime.now().isoformat()}",
        "\n## Description",
        description if description else "",
    ]

    # Add system information
    report.extend(
        [
            "\n## System Information",
            f"OS: {platform.system()} {platform.release()}",
            f"Python: {sys.version}",
            f"Elroy Version: {__version__}",
        ]
    )

    report.append("\n## Elroy Configuration")
    try:
        report.append("```")
        # Convert to dict and recursively obscure sensitive info
        config_dict = obscure_sensitive_info(asdict(context.config))
        report.append(pformat(config_dict, indent=2, width=80))
        report.append("```")
    except Exception as e:
        report.append(f"Error fetching config: {str(e)}")

    report.append(f"\n## Recent Logs (last {BUG_REPORT_LOG_LINES} lines)")
    try:
        logs = tail_elroy_logs(context, BUG_REPORT_LOG_LINES)
        report.append("```")
        report.append(logs)
        report.append("```")
    except Exception as e:
        report.append(f"Error fetching logs: {str(e)}")

    # Combine the report
    full_report = scrubadub.clean("\n".join(report))

    github_url = None
    base_url = os.path.join(REPO_ISSUES_URL, "new")
    params = {"title": title, "body": full_report}
    github_url = f"{base_url}?{urllib.parse.urlencode(params)}"
    webbrowser.open(github_url)


@experimental
def start_aider_session(context: ElroyContext, file_location: str = ".", comment: str = "") -> str:
    """
    Starts an aider session using a pseudo-terminal, taking over the screen.

    Args:
        context (ElroyContext): The Elroy context object.
        file_location (str): The file or directory location to start aider with. Defaults to current directory.
        comment (str): Initial text to be processed by aider as if it was typed. Defaults to empty string.

    Returns:
        str: A message indicating the result of the aider session start attempt.
    """
    from ..system_commands import print_context_messages

    try:
        # Ensure the file_location is an absolute path
        abs_file_location = os.path.abspath(file_location)

        # Determine the directory to change to
        if os.path.isfile(abs_file_location):
            change_dir = os.path.dirname(abs_file_location)
        else:
            change_dir = abs_file_location

        # Prepend /ask so the AI does not immediately start writing code.
        aider_context = (
            "{\n/ask "
            + client.query_llm(
                system="Your task is to provide context to a coding assistant AI. "
                "Given information about a conversation, return information about what the goal is, what the user needs help with, and/or any approaches that have been discussed. "
                "Focus your prompt specifically on what the coding Assistant needs to know. Do not include information about Elroy, personal information about the user, "
                "or anything that isn't relevant to what code the coding assistant will need to write.",
                prompt=pipe(
                    [
                        f"# Aider session file location: {abs_file_location}",
                        "# Comment: {comment}" if comment else None,
                        f"# Chat transcript: {print_context_messages(context)}",
                    ],
                    filter(lambda x: x is not None),
                    list,
                    "\n\n".join,
                ),  # type: ignore
            )
            + "\n}"
        )

        # Print debug information
        print(f"Starting aider session for location: {abs_file_location}")
        print(f"Current working directory: {os.getcwd()}")
        print(f"Changing directory to: {change_dir}")

        # Save the current terminal settings
        old_tty = termios.tcgetattr(sys.stdin)

        try:
            # Create a pseudo-terminal
            master_fd, slave_fd = pty.openpty()

            # Change the working directory
            os.chdir(change_dir)

            # Start the aider session
            process = subprocess.Popen(["aider"], stdin=slave_fd, stdout=slave_fd, stderr=slave_fd, preexec_fn=os.setsid)

            # Set the terminal to raw mode
            tty.setraw(sys.stdin.fileno())

            # Write the initial text to the master file descriptor
            if aider_context:
                os.write(master_fd, aider_context.encode())
                os.write(master_fd, b"\n")  # Add a newline to "send" the command
                time.sleep(0.5)  # Add a small delay to allow processing

            # Main loop to handle I/O
            while process.poll() is None:
                import select as os_select

                r, w, e = os_select.select([sys.stdin, master_fd], [], [], 0.1)
                if sys.stdin in r:
                    data = os.read(sys.stdin.fileno(), 1024)
                    os.write(master_fd, data)
                if master_fd in r:
                    data = os.read(master_fd, 1024)
                    if data:
                        os.write(sys.stdout.fileno(), data)
                    else:
                        break

            return_code = process.wait()

            if return_code == 0:
                return f"Aider session completed for location: {abs_file_location}"
            else:
                return f"Aider session exited with return code: {return_code}"
        finally:
            # Restore the original terminal settings
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_tty)
    except Exception as error:
        return f"Failed to start aider session: {str(error)}"
