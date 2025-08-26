from pathlib import Path
from typing import List, Optional

from ...core.ctx import ElroyContext
from ...core.logging import get_logger
from ...db.db_models import BackgroundIngestionConfig
from ...utils.clock import utc_now
from .queries import get_background_ingestion_config

logger = get_logger()


def create_background_ingestion_config(
    ctx: ElroyContext,
    watch_directory: str,
    recursive: bool = True,
    include_patterns: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
) -> BackgroundIngestionConfig:
    """Create a new background ingestion configuration for the user.

    Args:
        ctx: The Elroy context
        watch_directory: Directory to watch for changes
        recursive: Whether to watch subdirectories recursively
        include_patterns: List of glob patterns to include (empty means include all)
        exclude_patterns: List of glob patterns to exclude

    Returns:
        The created background ingestion configuration

    Raises:
        ValueError: If watch_directory doesn't exist or isn't a directory
    """
    # Validate directory exists
    dir_path = Path(watch_directory).expanduser().resolve()
    if not dir_path.exists():
        raise ValueError(f"Directory does not exist: {watch_directory}")
    if not dir_path.is_dir():
        raise ValueError(f"Path is not a directory: {watch_directory}")

    # Check if config already exists
    existing_config = get_background_ingestion_config(ctx)
    if existing_config:
        raise ValueError("Background ingestion configuration already exists. Use update_background_ingestion_config to modify.")

    # Create config
    config = BackgroundIngestionConfig(
        user_id=ctx.user_id,
        watch_directory=str(dir_path),
        is_active=True,
        recursive=recursive,
        include_patterns=",".join(include_patterns or []),
        exclude_patterns=",".join(exclude_patterns or []),
        last_scan_status="pending",
    )

    config = ctx.db.persist(config)
    logger.info(f"Created background ingestion config for directory: {watch_directory}")
    return config


def update_background_ingestion_config(
    ctx: ElroyContext,
    watch_directory: Optional[str] = None,
    is_active: Optional[bool] = None,
    recursive: Optional[bool] = None,
    include_patterns: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
) -> BackgroundIngestionConfig:
    """Update an existing background ingestion configuration.

    Args:
        ctx: The Elroy context
        watch_directory: New directory to watch (optional)
        is_active: Enable/disable background ingestion (optional)
        recursive: Whether to watch subdirectories recursively (optional)
        include_patterns: List of glob patterns to include (optional)
        exclude_patterns: List of glob patterns to exclude (optional)

    Returns:
        The updated background ingestion configuration

    Raises:
        ValueError: If no configuration exists or watch_directory is invalid
    """
    config = get_background_ingestion_config(ctx)
    if not config:
        raise ValueError("No background ingestion configuration exists. Use create_background_ingestion_config first.")

    # Validate new directory if provided
    if watch_directory is not None:
        dir_path = Path(watch_directory).expanduser().resolve()
        if not dir_path.exists():
            raise ValueError(f"Directory does not exist: {watch_directory}")
        if not dir_path.is_dir():
            raise ValueError(f"Path is not a directory: {watch_directory}")
        config.watch_directory = str(dir_path)

    # Update other fields
    if is_active is not None:
        config.is_active = is_active
    if recursive is not None:
        config.recursive = recursive
    if include_patterns is not None:
        config.include_patterns = ",".join(include_patterns)
    if exclude_patterns is not None:
        config.exclude_patterns = ",".join(exclude_patterns)

    config.updated_at = utc_now()
    config = ctx.db.persist(config)
    logger.info(f"Updated background ingestion config")
    return config


def delete_background_ingestion_config(ctx: ElroyContext) -> bool:
    """Delete the background ingestion configuration for the user.

    Args:
        ctx: The Elroy context

    Returns:
        True if configuration was deleted, False if no configuration existed
    """
    config = get_background_ingestion_config(ctx)
    if not config:
        return False

    ctx.db.delete(config)
    ctx.db.commit()
    logger.info("Deleted background ingestion config")
    return True


def mark_scan_completed(ctx: ElroyContext, success: bool = True) -> None:
    """Mark a background ingestion scan as completed.

    Args:
        ctx: The Elroy context
        success: Whether the scan completed successfully
    """
    config = get_background_ingestion_config(ctx)
    if config:
        config.last_full_scan = utc_now()
        config.last_scan_status = "success" if success else "error"
        config.updated_at = utc_now()
        ctx.db.persist(config)


def get_include_exclude_patterns(config: BackgroundIngestionConfig) -> tuple[List[str], List[str]]:
    """Parse include and exclude patterns from configuration.

    Args:
        config: The background ingestion configuration

    Returns:
        Tuple of (include_patterns, exclude_patterns)
    """
    include_patterns = [p.strip() for p in config.include_patterns.split(",") if p.strip()]
    exclude_patterns = [p.strip() for p in config.exclude_patterns.split(",") if p.strip()]
    return include_patterns, exclude_patterns
