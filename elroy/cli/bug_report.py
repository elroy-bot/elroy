import os
import platform
import sys
import urllib.parse
import webbrowser
import traceback
from datetime import datetime
from typing import Optional, Union, List


def create_bug_report(
    error: Exception,
    include_config: bool = True,
    include_logs: bool = True,
    log_lines: int = 50,
    create_github_issue: bool = False,
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
    # Generate title and description from the exception
    title = f"Error: {error.__class__.__name__}"
    description = f"Exception occurred: {str(error)}\n\nTraceback:\n{''.join(traceback.format_tb(error.__traceback__))}"

    # Start building the report
    report = [
        f"# Bug Report: {title}",
        f"\nCreated: {datetime.now().isoformat()}",
        "\n## Description",
        description,
    ]

    # Add system information
    report.extend([
        "\n## System Information",
        f"OS: {platform.system()} {platform.release()}",
        f"Python: {sys.version}",
        f"Elroy Environment: {os.environ.get('ELROY_ENV', 'unknown')}"
    ])

    # Add configuration if requested
    if include_config:
        report.append("\n## Elroy Configuration")
        try:
            from elroy.system_commands import print_elroy_config
            config = print_elroy_config()
            report.append("```")
            report.append(str(config))
            report.append("```")
        except Exception as e:
            report.append(f"Error fetching config: {str(e)}")

    # Add logs if requested
    if include_logs:
        report.append(f"\n## Recent Logs (last {log_lines} lines)")
        try:
            from elroy.system_commands import tail_elroy_logs
            logs = tail_elroy_logs(lines=log_lines)
            report.append("```")
            report.append(logs)
            report.append("```")
        except Exception as e:
            report.append(f"Error fetching logs: {str(e)}")

    # Combine the report
    full_report = "\n".join(report)

    # Handle GitHub issue creation if requested
    github_url = None
    if create_github_issue:
        base_url = "https://github.com/elroy-bot/elroy/issues/new"
        params = {"title": title, "body": full_report}
        github_url = f"{base_url}?{urllib.parse.urlencode(params)}"
        webbrowser.open(github_url)

    return {
        "report": full_report,
        "github_url": github_url,
        "success": True
    }
