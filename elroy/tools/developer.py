import os
import platform
import sys
import urllib.parse
import webbrowser
from datetime import datetime
from typing import Optional

from rich.table import Table
from rich.text import Text

from .. import __version__
from ..config.constants import BUG_REPORT_LOG_LINES, REPO_ISSUES_URL, tool
from ..config.ctx import ElroyContext
from ..config.paths import get_home_dir, get_log_file_path


@tool
def tail_elroy_logs(lines: int = 10) -> str:
    """
    Returns the last `lines` of the Elroy logs.
    Useful for troubleshooting in cases where errors occur (especially with tool calling).

    Args:
        context (ElroyContext): context obj
        lines (int, optional): Number of lines to return. Defaults to 10.

    Returns:
        str: The last `lines` of the Elroy logs
    """
    with open(get_log_file_path(), "r") as f:
        return "".join(f.readlines()[-lines:])


def print_config(ctx: ElroyContext) -> Table:
    """
    Prints the current Elroy configuration in a formatted table.
    Useful for troubleshooting and verifying the current configuration.

    Args:
        ctx (ElroyContext): context obj
    """
    return do_print_config(ctx, False)


def do_print_config(ctx: ElroyContext, show_secrets=False) -> Table:
    """
    Prints the current Elroy configuration in a formatted table.
    Useful for troubleshooting and verifying the current configuration.

    Args:
        ctx (ElroyContext): context obj
    """

    sections = {
        "System Information": {
            "OS": f"{platform.system()} {platform.release()}",
            "Python Version": platform.python_version(),
            "Python Location": sys.executable,
            "Elroy Version": __version__,
            "Elroy Home Dir": get_home_dir(),
            "Config Path": ctx.config_path,
        },
        "Basic Configuration": {
            "Debug Mode": ctx.debug,
            "Default Assistant Name": ctx.default_assistant_name,
            "User Token": ctx.user_token,
            "Database URL": (
                "postgresql://" + "*" * 8
                if not show_secrets and ctx.params.database_url.startswith("postgresql")
                else ctx.params.database_url
            ),
        },
        "Model Configuration": {
            "Chat Model": ctx.params.chat_model,
            "Embedding Model": ctx.params.embedding_model,
            "Embedding Model Size": ctx.params.embedding_model_size,
            "Caching Enabled": ctx.params.enable_caching,
        },
        "API Configuration": {
            "OpenAI API Base": ctx.params.openai_api_base or "None",
            "OpenAI Embedding API Base": ctx.params.openai_embedding_api_base or "None",
            "OpenAI Organization": ctx.params.openai_organization or "None",
            "OpenAI API key": "*" * 8 if ctx.params.openai_api_key and not show_secrets else ctx.params.openai_api_key or "None",
            "Anthropic API key": "*" * 8 if ctx.params.anthropic_api_key and not show_secrets else ctx.params.anthropic_api_key or "None",
        },
        "Context Management": {
            "Max Assistant Loops": ctx.max_assistant_loops,
            "Context Refresh Trigger Tokens": ctx.context_refresh_trigger_tokens,
            "Context Refresh Target Tokens": ctx.context_refresh_target_tokens,
            "Max Context Age (minutes)": ctx.params.max_context_age_minutes,
        },
        "Memory Management": {
            "Memory Cluster Similarity": ctx.memory_cluster_similarity_threshold,
            "Max Memory Cluster Size": ctx.max_memory_cluster_size,
            "Min Memory Cluster Size": ctx.min_memory_cluster_size,
            "Memories Between Consolidation": ctx.memories_between_consolidation,
            "L2 Memory Relevance Distance": ctx.l2_memory_relevance_distance_threshold,
        },
        "UI Configuration": {
            "Show Internal Thought": ctx.show_internal_thought,
            "System Message Color": Text(ctx.params.system_message_color, style=ctx.params.system_message_color),
            "Assistant Color": Text(ctx.params.assistant_color, style=ctx.params.assistant_color),
            "User Input Color": Text(ctx.params.user_input_color, style=ctx.params.user_input_color),
            "Warning Color": Text(ctx.params.warning_color, style=ctx.params.warning_color),
            "Internal Thought Color": Text(ctx.params.internal_thought_color, style=ctx.params.internal_thought_color),
        },
    }

    table = Table(title="Elroy Configuration", show_header=True, header_style="bold magenta")
    table.add_column("Section")
    table.add_column("Setting")
    table.add_column("Value")

    for section, settings in sections.items():
        for setting, value in settings.items():
            table.add_row(
                section if setting == list(settings.keys())[0] else "",  # Only show section name once
                setting,
                value if isinstance(value, Text) else str(value),
            )

    return table


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
    full_report = "\n".join(report)

    github_url = None
    base_url = os.path.join(REPO_ISSUES_URL, "new")
    params = {"title": title, "body": full_report}
    github_url = f"{base_url}?{urllib.parse.urlencode(params)}"
    webbrowser.open(github_url)
