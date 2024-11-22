import os
import platform
import sys
import urllib.parse
import webbrowser
from datetime import datetime


def create_bug_report(
    title: str = None,
    description: str = None,
    steps_to_reproduce: list = None,
    include_config: bool = True,
    include_logs: bool = True,
    log_lines: int = 50,
    create_github_issue: bool = False,
) -> dict:
    """
    Interactive bug report generator that collects user input and system information.
    """
    # Collect user input if not provided
    if not title:
        title = input("Bug Title: ")
    if not description:
        description = input("Description:\n")
    if not steps_to_reproduce:
        steps = []
        print("Steps to reproduce (enter empty line when done):")
        while True:
            step = input(f"Step {len(steps) + 1}: ")
            if not step:
                break
            steps.append(step)
        steps_to_reproduce = steps

    # Start building the report
    report = [
        f"# Bug Report: {title}",
        f"[/]nCreated: {datetime.now().isoformat()}",
        "[/]n## Description",
        description,
        "\n## Steps to Reproduce",
    ]
    for i, step in enumerate(steps_to_reproduce, 1):
        report.append(f"{i}. {step}")

    # Add system information
    report.extend(
        [
            "\n## System Information",
            f"OS: {platform.system()} {platform.release()}",
            f"Python: {sys.version}",
            f"Elroy Environment: {os.environ.get('ELROY_ENV', 'unknown')}",
        ]
    )

    # Add configuration if requested
    if include_config:
        report.append("\n## Elroy Configuration")
        try:
            config = print_elroy_config()  # Assuming this is available
            report.append("```")
            report.append(str(config))
            report.append("```")
        except Exception as e:
            report.append(f"Error fetching config: {str(e)}")

    # Add logs if requested
    if include_logs:
        report.append(f"\n## Recent Logs (last {log_lines} lines)")
        try:
            logs = tail_elroy_logs(lines=log_lines)  # Assuming this is available
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
        base_url = "https://github.com/yourusername/elroy/issues/new"
        params = {"title": title, "body": full_report}
        github_url = f"{base_url}?{urllib.parse.urlencode(params)}"
        webbrowser.open(github_url)

    return {"report": full_report, "github_url": github_url, "success": True}
