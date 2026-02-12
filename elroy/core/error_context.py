"""Error context gathering utilities for self-diagnosis.

This module provides functions to gather comprehensive diagnostic information
when errors occur, including traceback, logs, system info, and configuration.
"""

import platform
import sys
import traceback
from typing import Any, Dict

from pydantic import BaseModel

from .. import __version__
from ..config.paths import get_home_dir
from ..core.ctx import ElroyContext
from ..tools.developer import tail_elroy_logs


class DiagnosticContext(BaseModel):
    """Complete context for error diagnosis."""

    error_type: str
    error_message: str
    traceback: str
    recent_logs: str
    config_summary: Dict[str, Any]
    system_info: Dict[str, str]
    chat_model: str


def gather_diagnostic_context(ctx: ElroyContext, error: Exception, max_log_lines: int = 50) -> DiagnosticContext:
    """Gather all diagnostic information needed to analyze an error.

    Args:
        ctx: ElroyContext for accessing configuration
        error: The exception that occurred
        max_log_lines: Number of log lines to include

    Returns:
        DiagnosticContext with all error information
    """
    # Gather traceback
    tb_lines = traceback.format_exception(type(error), error, error.__traceback__)
    traceback_str = "".join(tb_lines)

    # Gather recent logs
    try:
        logs = tail_elroy_logs(max_log_lines)
    except Exception as e:
        logs = f"Error fetching logs: {str(e)}"

    # Gather system information
    system_info = {
        "os": f"{platform.system()} {platform.release()}",
        "python_version": platform.python_version(),
        "python_location": sys.executable,
        "elroy_version": __version__,
        "elroy_home_dir": str(get_home_dir()),
        "config_path": ctx.config_path or "default",
    }

    # Gather configuration summary (non-sensitive info)
    config_summary = {
        "debug_mode": ctx.debug,
        "chat_model": ctx.chat_model.name,
        "fast_model": ctx.fast_model.name,
        "embedding_model": ctx.embedding_model.name,
        "database_type": "postgresql" if ctx.database_config.database_url.startswith("postgresql") else "sqlite",
        "vector_backend": ctx.database_config.vector_backend,
        "custom_tools_enabled": bool(ctx.tool_config.custom_tools_path),
        "shell_commands_enabled": ctx.tool_config.shell_commands,
    }

    return DiagnosticContext(
        error_type=error.__class__.__name__,
        error_message=str(error),
        traceback=traceback_str,
        recent_logs=logs,
        config_summary=config_summary,
        system_info=system_info,
        chat_model=ctx.chat_model.name,
    )
