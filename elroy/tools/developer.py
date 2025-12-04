import os
import platform
import sys
import urllib.parse
import webbrowser
from typing import Optional

from rich.table import Table
from rich.text import Text

from .. import __version__
from ..config.paths import get_home_dir, get_log_file_path
from ..core.constants import BUG_REPORT_LOG_LINES, REPO_ISSUES_URL, user_only_tool
from ..core.ctx import ElroyContext
from ..core.logging import get_logger
from ..utils.clock import utc_now

logger = get_logger()


@user_only_tool
def tail_elroy_logs(lines: int = 10) -> str:
    """
    Returns the last `lines` of the Elroy logs.
    Useful for troubleshooting in cases where errors occur (especially with tool calling).

    Args:
        lines (int, optional): Number of lines to return from the end of the log file. Defaults to 10.

    Returns:
        str: The concatenated last N lines of the Elroy log file as a single string
    """
    with open(get_log_file_path(), "r") as f:
        return "".join(f.readlines()[-lines:])


@user_only_tool
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
                if not show_secrets and ctx.database_config.database_url.startswith("postgresql")
                else ctx.database_config.database_url
            ),
        },
        "Model Configuration": {
            "Chat Model": ctx.chat_model.name,
            "Embedding Model": ctx.embedding_model.name,
            "Embedding Model Size": ctx.model_config.embedding_model_size,
            "Caching Enabled": ctx.model_config.enable_caching,
        },
        "API Configuration": {
            "Chat API Base": ctx.chat_model.api_base or "None (May be read from env vars)",
            "Chat API Key": (
                "*" * 8 if ctx.chat_model.api_key and not show_secrets else ctx.chat_model.api_key or "None (May be read from env vars)"
            ),
            "Embeddings API Base": ctx.embedding_model.api_base or "None (May be read from env vars)",
            "Embeddings API Key": (
                "*" * 8
                if ctx.embedding_model.api_key and not show_secrets
                else ctx.embedding_model.api_key or "None (May be read from env vars)"
            ),
        },
        "Context Management": {
            "Max Assistant Loops": ctx.max_assistant_loops,
            "Max tokens": ctx.max_tokens,
            "Context Refresh Target Tokens": ctx.context_refresh_target_tokens,
            "Max Context Age (minutes)": ctx.memory_config.max_context_age_minutes,
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
            "System Message Color": Text(ctx.ui_config.system_message_color, style=ctx.ui_config.system_message_color),
            "Assistant Color": Text(ctx.ui_config.assistant_color, style=ctx.ui_config.assistant_color),
            "User Input Color": Text(ctx.ui_config.user_input_color, style=ctx.ui_config.user_input_color),
            "Warning Color": Text(ctx.ui_config.warning_color, style=ctx.ui_config.warning_color),
            "Internal Thought Color": Text(ctx.ui_config.internal_thought_color, style=ctx.ui_config.internal_thought_color),
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


@user_only_tool
def create_bug_report(
    ctx: ElroyContext,
    title: str,
    description: Optional[str],
) -> None:
    """
    Generate a bug report and open it as a GitHub issue.

    Args:
        title: The title for the bug report
        description: Detailed description of the issue
    """
    # Start building the report
    report = [
        f"# Bug Report: {title}",
        f"\nCreated: {utc_now().isoformat()}",
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
        logs = tail_elroy_logs(BUG_REPORT_LOG_LINES)
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
