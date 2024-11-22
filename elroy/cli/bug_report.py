import os
import platform
import sys
import traceback
from dataclasses import asdict
from pprint import pformat
import urllib.parse
import webbrowser
from datetime import datetime

from ..config.config import ElroyContext
from ..config.constants import REPO_ISSUES_URL
from ..io.cli import CliIO
from ..system_commands import tail_elroy_logs

LOG_LINES = 15


async def create_bug_report_from_exception_if_confirmed(context: ElroyContext[CliIO], error: Exception) -> dict:
    if await context.io.prompt_user("An error occurred, would you like to open a pre-filled bug report? (y/n)") == "y":
        return create_bug_report(
            context,
            f"Error: {error.__class__.__name__}",
            f"Exception occurred: {str(error)}\n\nTraceback:\n{''.join(traceback.format_tb(error.__traceback__))}",
        )


def create_bug_report(
    context: ElroyContext,
    title: str,
    description: str,
) -> dict:
    """
    Bug report generator that works from an exception.

    Args:
        error: Exception that triggered the bug report
        include_config: Whether to include Elroy config
        include_logs: Whether to include recent logs
        log_lines: Number of log lines to include
        create_github_issue: Whether to open a GitHub issue
    """
    # Start building the report
    report = [
        f"# Bug Report: {title}",
        f"\nCreated: {datetime.now().isoformat()}",
        "\n## Description",
        description,
    ]

    # Add system information
    report.extend(
        [
            "\n## System Information",
            f"OS: {platform.system()} {platform.release()}",
            f"Python: {sys.version}",
        ]
    )

    # Add configuration if requested
    report.append("\n## Elroy Configuration")
    try:
        report.append("```")
        report.append(str(context.config))
        report.append("```")
    except Exception as e:
        report.append(f"Error fetching config: {str(e)}")

    # Add logs if requested
    report.append(f"\n## Recent Logs (last {LOG_LINES} lines)")
    try:
        logs = tail_elroy_logs(context, LOG_LINES)
        report.append("```")
        report.append(logs)
        report.append("```")
    except Exception as e:
        report.append(f"Error fetching logs: {str(e)}")

    # Combine the report
    full_report = "\n".join(report)

    # Handle GitHub issue creation if requested
    github_url = None
    base_url = os.path.join(REPO_ISSUES_URL, "new")
    params = {"title": title, "body": full_report}
    github_url = f"{base_url}?{urllib.parse.urlencode(params)}"
    webbrowser.open(github_url)

    return {"report": full_report, "github_url": github_url, "success": True}
