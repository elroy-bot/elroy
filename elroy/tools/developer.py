from pathlib import Path

from rich.table import Table
from rich.text import Text

from ..config.paths import get_log_file_path
from ..core.constants import user_only_tool
from ..core.ctx import ElroyConfig
from ..core.logging import get_logger
from ..core.runtime import ConfigReportRuntime, build_config_report_runtime, build_system_info_runtime

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
    with Path(get_log_file_path()).open() as f:
        return "".join(f.readlines()[-lines:])


@user_only_tool
def print_config(ctx: ElroyConfig) -> Table:
    """
    Prints the current Elroy configuration in a formatted table.
    Useful for troubleshooting and verifying the current configuration.

    Args:
        ctx (ElroyConfig): config obj
    """
    return do_print_config(build_config_report_runtime(ctx), False)


def do_print_config(runtime: ConfigReportRuntime, show_secrets: bool = False) -> Table:
    """
    Prints the current Elroy configuration in a formatted table.
    Useful for troubleshooting and verifying the current configuration.

    Args:
        runtime (ConfigReportRuntime): formatted config-report runtime
    """

    sections = {
        "System Information": {
            **build_system_info_runtime(),
            "Config Path": runtime.config_path,
        },
        "Basic Configuration": {
            "Debug Mode": runtime.debug,
            "Default Assistant Name": runtime.default_assistant_name,
            "User Token": runtime.user_token,
            "Database URL": runtime.database_url,
        },
        "Model Configuration": {
            "Chat Model": runtime.chat_model_name,
            "Embedding Model": runtime.embedding_model_name,
            "Embedding Model Size": runtime.embedding_model_size,
            "Caching Enabled": runtime.caching_enabled,
        },
        "API Configuration": {
            "Chat API Base": runtime.chat_api_base,
            "Chat API Key": (
                "*" * 8 if runtime.chat_api_key and not show_secrets else runtime.chat_api_key or "None (May be read from env vars)"
            ),
            "Embeddings API Base": runtime.embeddings_api_base,
            "Embeddings API Key": (
                "*" * 8
                if runtime.embeddings_api_key and not show_secrets
                else runtime.embeddings_api_key or "None (May be read from env vars)"
            ),
        },
        "Context Management": {
            "Max Assistant Loops": runtime.max_assistant_loops,
            "Max tokens": runtime.max_tokens,
            "Context Refresh Target Tokens": runtime.context_refresh_target_tokens,
            "Max Context Age (minutes)": runtime.max_context_age_minutes,
        },
        "Memory Management": {
            "Memory Dir": runtime.memory_dir,
            "Memory Cluster Similarity": runtime.memory_cluster_similarity,
            "Max Memory Cluster Size": runtime.max_memory_cluster_size,
            "Min Memory Cluster Size": runtime.min_memory_cluster_size,
            "Memories Between Consolidation": runtime.memories_between_consolidation,
            "L2 Memory Relevance Distance": runtime.l2_memory_relevance_distance,
        },
        "UI Configuration": {
            "Show Internal Thought": runtime.show_internal_thought,
            "System Message Color": runtime.system_message_color,
            "Assistant Color": runtime.assistant_color,
            "User Input Color": runtime.user_input_color,
            "Warning Color": runtime.warning_color,
            "Internal Thought Color": runtime.internal_thought_color,
        },
    }

    table = Table(title="Elroy Configuration", show_header=True, header_style="bold magenta")
    table.add_column("Section")
    table.add_column("Setting")
    table.add_column("Value")

    for section, settings in sections.items():
        for setting, value in settings.items():
            table.add_row(
                section if setting == next(iter(settings.keys())) else "",  # Only show section name once
                setting,
                value if isinstance(value, Text) else str(value),
            )

    return table
