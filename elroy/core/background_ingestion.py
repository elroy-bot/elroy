import time
from pathlib import Path
from threading import Lock
from typing import Dict, Optional

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from ..core.ctx import ElroyContext
from ..core.logging import get_logger
from ..core.session import dbsession
from ..repository.background_ingestion.operations import (
    get_include_exclude_patterns,
    mark_scan_completed,
)
from ..repository.background_ingestion.queries import (
    get_active_background_ingestion_config,
)
from ..repository.documents.operations import DocIngestStatus, do_ingest, do_ingest_dir
from ..utils.clock import utc_now

logger = get_logger()


class BackgroundIngestionHandler(FileSystemEventHandler):
    """File system event handler for background document ingestion."""

    def __init__(self, ctx: ElroyContext):
        super().__init__()
        self.ctx = ctx
        self.recent_files: Dict[str, float] = {}  # Track recently processed files to avoid duplicates
        self.lock = Lock()  # Thread safety for recent_files

    def _should_process_file(self, file_path: str) -> bool:
        """Check if a file should be processed based on timing and patterns."""

        # Get current config
        with dbsession(self.ctx):
            config = get_active_background_ingestion_config(self.ctx)
            if not config:
                return False

            include_patterns, exclude_patterns = get_include_exclude_patterns(config)

        path = Path(file_path)

        # Check if file exists and is a file (not directory)
        if not path.exists() or not path.is_file():
            return False

        # Import and use existing filtering logic
        from ..repository.documents.operations import should_process_file

        if not should_process_file(path, include_patterns, exclude_patterns):
            return False

        # Prevent duplicate processing of recently modified files
        with self.lock:
            current_time = time.time()
            if file_path in self.recent_files:
                if current_time - self.recent_files[file_path] < 5.0:  # 5 second cooldown
                    return False
            self.recent_files[file_path] = current_time

            # Clean up old entries (older than 1 minute)
            cutoff_time = current_time - 60
            self.recent_files = {k: v for k, v in self.recent_files.items() if v > cutoff_time}

        return True

    def _process_file(self, file_path: str) -> None:
        """Process a single file for ingestion."""
        try:
            # Create a new context with fresh DB session for this thread
            new_ctx = ElroyContext(**vars(self.ctx.params))
            with dbsession(new_ctx):
                result = do_ingest(new_ctx, Path(file_path), force_refresh=False)

                if result in [DocIngestStatus.SUCCESS, DocIngestStatus.UPDATED]:
                    logger.info(f"Background ingestion: {result.name} for {file_path}")
                elif result == DocIngestStatus.MOVED:
                    logger.info(f"Background ingestion: Document moved, updated address for {file_path}")
                else:
                    logger.debug(f"Background ingestion: {result.name} for {file_path}")

        except Exception as e:
            logger.error(f"Background ingestion failed for {file_path}: {str(e)}", exc_info=True)

    def on_created(self, event):
        """Handle file creation events."""
        if not event.is_directory and self._should_process_file(event.src_path):
            logger.debug(f"File created: {event.src_path}")
            self._process_file(event.src_path)

    def on_modified(self, event):
        """Handle file modification events."""
        if not event.is_directory and self._should_process_file(event.src_path):
            logger.debug(f"File modified: {event.src_path}")
            self._process_file(event.src_path)

    def on_moved(self, event):
        """Handle file move events."""
        if not event.is_directory and self._should_process_file(event.dest_path):
            logger.debug(f"File moved: {event.src_path} -> {event.dest_path}")
            self._process_file(event.dest_path)


class BackgroundIngestionService:
    """Service to manage background document ingestion."""

    def __init__(self, ctx: ElroyContext):
        self.ctx = ctx
        self.observer: Optional[Observer] = None
        self.handler: Optional[BackgroundIngestionHandler] = None
        self.is_running = False

    def start(self) -> bool:
        """Start the background ingestion service.

        Returns:
            True if service started successfully, False otherwise
        """
        if self.is_running:
            logger.warning("Background ingestion service is already running")
            return False

        if not self.ctx.background_ingestion_enabled:
            logger.info("Background ingestion is globally disabled")
            return False

        config = get_active_background_ingestion_config(self.ctx)
        if not config:
            logger.debug("No active background ingestion configuration found")
            return False

        watch_directory = Path(config.watch_directory)
        if not watch_directory.exists() or not watch_directory.is_dir():
            logger.error(f"Watch directory does not exist or is not a directory: {config.watch_directory}")
            return False

        try:
            self.handler = BackgroundIngestionHandler(self.ctx)
            self.observer = Observer()
            self.observer.schedule(self.handler, str(watch_directory), recursive=config.recursive)
            self.observer.start()
            self.is_running = True
            logger.info(f"Started background ingestion service for directory: {watch_directory}")
            return True

        except Exception as e:
            logger.error(f"Failed to start background ingestion service: {str(e)}", exc_info=True)
            return False

    def stop(self) -> bool:
        """Stop the background ingestion service.

        Returns:
            True if service stopped successfully, False otherwise
        """
        if not self.is_running:
            return False

        try:
            if self.observer:
                self.observer.stop()
                self.observer.join(timeout=5.0)  # Wait up to 5 seconds
                self.observer = None

            self.handler = None
            self.is_running = False
            logger.info("Stopped background ingestion service")
            return True

        except Exception as e:
            logger.error(f"Error stopping background ingestion service: {str(e)}", exc_info=True)
            return False

    def restart(self) -> bool:
        """Restart the background ingestion service.

        Returns:
            True if service restarted successfully, False otherwise
        """
        self.stop()
        return self.start()

    def is_service_running(self) -> bool:
        """Check if the service is currently running."""
        return self.is_running and self.observer is not None


def perform_full_scan(ctx: ElroyContext) -> bool:
    """Perform a full scan of the configured watch directory.

    Args:
        ctx: The Elroy context

    Returns:
        True if scan completed successfully, False otherwise
    """
    config = get_active_background_ingestion_config(ctx)
    if not config:
        logger.debug("No active background ingestion configuration for full scan")
        return False

    watch_directory = Path(config.watch_directory)
    if not watch_directory.exists() or not watch_directory.is_dir():
        logger.error(f"Watch directory does not exist for full scan: {config.watch_directory}")
        mark_scan_completed(ctx, success=False)
        return False

    try:
        logger.info(f"Starting full background ingestion scan of directory: {watch_directory}")

        include_patterns, exclude_patterns = get_include_exclude_patterns(config)

        # Use existing directory ingestion logic
        total_processed = 0
        for status_update in do_ingest_dir(
            ctx, watch_directory, force_refresh=False, recursive=config.recursive, include=include_patterns, exclude=exclude_patterns
        ):
            # Get final status counts
            if DocIngestStatus.PENDING not in status_update or status_update[DocIngestStatus.PENDING] == 0:
                total_processed = sum(status_update.values())
                success_count = status_update.get(DocIngestStatus.SUCCESS, 0)
                updated_count = status_update.get(DocIngestStatus.UPDATED, 0)
                unchanged_count = status_update.get(DocIngestStatus.UNCHANGED, 0)
                moved_count = status_update.get(DocIngestStatus.MOVED, 0)

                logger.info(
                    f"Full scan completed: {total_processed} files processed "
                    f"({success_count} new, {updated_count} updated, {moved_count} moved, {unchanged_count} unchanged)"
                )
                break

        mark_scan_completed(ctx, success=True)
        return True

    except Exception as e:
        logger.error(f"Full background ingestion scan failed: {str(e)}", exc_info=True)
        mark_scan_completed(ctx, success=False)
        return False


def should_run_full_scan(ctx: ElroyContext) -> bool:
    """Check if a full scan should be run based on configuration and last scan time.

    Args:
        ctx: The Elroy context

    Returns:
        True if a full scan should be run, False otherwise
    """
    config = get_active_background_ingestion_config(ctx)
    if not config:
        return False

    if not config.last_full_scan:
        return True  # Never run before

    # Check if enough time has passed since last scan
    hours_since_scan = (utc_now() - config.last_full_scan).total_seconds() / 3600
    return hours_since_scan >= ctx.background_ingestion_full_scan_interval_hours
