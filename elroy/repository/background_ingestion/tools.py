from pathlib import Path
from typing import Optional

from ...core.constants import tool
from ...core.ctx import ElroyContext
from .operations import (
    create_background_ingestion_config,
    delete_background_ingestion_config,
    get_include_exclude_patterns,
    update_background_ingestion_config,
)
from .queries import get_background_ingestion_config


@tool
def setup_background_ingestion(
    ctx: ElroyContext,
    directory: str,
    recursive: bool = True,
    include_patterns: Optional[str] = None,
    exclude_patterns: Optional[str] = None,
) -> str:
    """Set up background document ingestion for a directory.

    This enables automatic monitoring and ingestion of documents in the specified directory.
    Files will be ingested automatically when they are created or modified.

    Args:
        directory: Path to the directory to monitor for documents
        recursive: Whether to also monitor subdirectories (default: True)
        include_patterns: Comma-separated glob patterns for files to include (e.g. "*.md,*.txt")
        exclude_patterns: Comma-separated glob patterns for files to exclude (e.g. "*.log,*.tmp")

    Returns:
        Confirmation message about the setup
    """
    try:
        # Convert directory to absolute path
        dir_path = Path(directory).expanduser().resolve()

        # Parse patterns
        include_list = [p.strip() for p in include_patterns.split(",")] if include_patterns else []
        exclude_list = [p.strip() for p in exclude_patterns.split(",")] if exclude_patterns else []

        # Check if config already exists
        existing_config = get_background_ingestion_config(ctx)
        if existing_config:
            return f"Background ingestion is already configured for directory: {existing_config.watch_directory}. Use update_background_ingestion to modify settings."

        # Create new configuration
        config = create_background_ingestion_config(
            ctx=ctx,
            watch_directory=str(dir_path),
            recursive=recursive,
            include_patterns=include_list,
            exclude_patterns=exclude_list,
        )

        pattern_info = []
        if include_list:
            pattern_info.append(f"including patterns: {', '.join(include_list)}")
        if exclude_list:
            pattern_info.append(f"excluding patterns: {', '.join(exclude_list)}")

        pattern_str = f" ({', '.join(pattern_info)})" if pattern_info else ""
        recursive_str = " (recursive)" if recursive else " (non-recursive)"

        return f"Background ingestion enabled for directory: {dir_path}{recursive_str}{pattern_str}. Documents will be automatically ingested when created or modified."

    except ValueError as e:
        return f"Error setting up background ingestion: {str(e)}"


@tool
def update_background_ingestion(
    ctx: ElroyContext,
    directory: Optional[str] = None,
    enable: Optional[bool] = None,
    recursive: Optional[bool] = None,
    include_patterns: Optional[str] = None,
    exclude_patterns: Optional[str] = None,
) -> str:
    """Update background document ingestion settings.

    Args:
        directory: New directory to monitor (optional)
        enable: Enable or disable background ingestion (optional)
        recursive: Whether to monitor subdirectories recursively (optional)
        include_patterns: Comma-separated glob patterns for files to include (optional)
        exclude_patterns: Comma-separated glob patterns for files to exclude (optional)

    Returns:
        Confirmation message about the update
    """
    try:
        # Parse patterns if provided
        include_list = [p.strip() for p in include_patterns.split(",")] if include_patterns else None
        exclude_list = [p.strip() for p in exclude_patterns.split(",")] if exclude_patterns else None

        # Update configuration
        config = update_background_ingestion_config(
            ctx=ctx,
            watch_directory=directory,
            is_active=enable,
            recursive=recursive,
            include_patterns=include_list,
            exclude_patterns=exclude_list,
        )

        return f"Background ingestion settings updated. Currently monitoring: {config.watch_directory} ({'enabled' if config.is_active else 'disabled'})"

    except ValueError as e:
        return f"Error updating background ingestion: {str(e)}"


@tool
def get_background_ingestion_status(ctx: ElroyContext) -> str:
    """Get the current status of background document ingestion.

    Returns:
        Current background ingestion configuration and status
    """
    config = get_background_ingestion_config(ctx)

    if not config:
        return "Background document ingestion is not configured. Use setup_background_ingestion to enable it."

    status = "enabled" if config.is_active else "disabled"
    recursive_str = "recursive" if config.recursive else "non-recursive"

    include_patterns, exclude_patterns = get_include_exclude_patterns(config)

    status_parts = [
        f"Background document ingestion is {status}",
        f"Monitoring directory: {config.watch_directory} ({recursive_str})",
    ]

    if include_patterns:
        status_parts.append(f"Including patterns: {', '.join(include_patterns)}")
    if exclude_patterns:
        status_parts.append(f"Excluding patterns: {', '.join(exclude_patterns)}")

    if config.last_full_scan:
        status_parts.append(f"Last full scan: {config.last_full_scan} (status: {config.last_scan_status})")
    else:
        status_parts.append("No full scan completed yet")

    return "\n".join(status_parts)


@tool
def disable_background_ingestion(ctx: ElroyContext) -> str:
    """Disable background document ingestion without removing the configuration.

    Returns:
        Confirmation message
    """
    try:
        config = update_background_ingestion_config(ctx=ctx, is_active=False)
        return f"Background ingestion disabled for directory: {config.watch_directory}. Use update_background_ingestion to re-enable."
    except ValueError as e:
        return f"Error disabling background ingestion: {str(e)}"


@tool
def remove_background_ingestion(ctx: ElroyContext) -> str:
    """Completely remove background document ingestion configuration.

    Returns:
        Confirmation message
    """
    success = delete_background_ingestion_config(ctx)

    if success:
        return "Background document ingestion configuration removed completely."
    else:
        return "No background ingestion configuration found to remove."
