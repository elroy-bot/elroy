import os
import platform
import sys
import urllib.parse
import webbrowser
from datetime import datetime
from pprint import pformat
from typing import Optional

import scrubadub
from toolz import pipe
from toolz.curried import keyfilter

from .. import __version__
from ..config.constants import BUG_REPORT_LOG_LINES, REPO_ISSUES_URL
from ..config.ctx import ElroyContext
from ..utils.ops import experimental


@experimental
def tail_elroy_logs(ctx: ElroyContext, lines: int = 10) -> str:
    """
    Returns the last `lines` of the Elroy logs.
    Useful for troubleshooting in cases where errors occur (especially with tool calling).

    Args:
        context (ElroyContext): context obj
        lines (int, optional): Number of lines to return. Defaults to 10.

    Returns:
        str: The last `lines` of the Elroy logs
    """
    with open(ctx.log_file_path, "r") as f:
        return "".join(f.readlines()[-lines:])


def print_elroy_config(ctx: ElroyContext) -> str:
    """
    Prints the current Elroy configuration.
    Useful for troubleshooting and verifying the current configuration.

    Args:
        context (ElroyContext): context obj

    Returns:
        str: The current Elroy configuration
    """
    return pipe(
        vars(ctx),
        # lambda d: obscure_sensitive_info(d) if scrub else d,
        keyfilter(lambda k: not k.startswith("_")),
        lambda x: pformat(x, indent=2, width=80),
    )  # type: ignore


def create_bug_report(
    ctx: ElroyContext,
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

    report.append(f"\n## Recent Logs (last {BUG_REPORT_LOG_LINES} lines)")
    try:
        logs = tail_elroy_logs(ctx, BUG_REPORT_LOG_LINES)
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
