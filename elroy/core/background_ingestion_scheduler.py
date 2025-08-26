from datetime import datetime, timedelta
from typing import Optional

from ..core.async_tasks import get_scheduler, schedule_task
from ..core.background_ingestion import (
    BackgroundIngestionService,
    perform_full_scan,
    should_run_full_scan,
)
from ..core.ctx import ElroyContext
from ..core.logging import get_logger
from ..repository.background_ingestion.queries import (
    get_active_background_ingestion_config,
)

logger = get_logger()

# Global service instance
_background_service: Optional[BackgroundIngestionService] = None


def start_background_ingestion_for_user(ctx: ElroyContext) -> bool:
    """Start background ingestion service and schedule periodic tasks for a user.

    Args:
        ctx: The Elroy context

    Returns:
        True if started successfully, False otherwise
    """
    global _background_service

    if not ctx.background_ingestion_enabled:
        logger.debug("Background ingestion is globally disabled")
        return False

    # Check if user has active config
    config = get_active_background_ingestion_config(ctx)
    if not config:
        logger.debug("No active background ingestion config found for user")
        return False

    # Start file system watching service
    if _background_service is None:
        _background_service = BackgroundIngestionService(ctx)

    if not _background_service.is_service_running():
        success = _background_service.start()
        if not success:
            return False

    # Schedule periodic full scans
    schedule_periodic_full_scan(ctx)

    # Run initial full scan if needed
    if should_run_full_scan(ctx):
        schedule_task(
            perform_full_scan,
            ctx,
            delay_seconds=10,  # Run after 10 seconds to allow app to fully start
        )

    logger.info("Background ingestion started for user")
    return True


def stop_background_ingestion() -> None:
    """Stop the background ingestion service."""
    global _background_service

    if _background_service:
        _background_service.stop()
        _background_service = None
        logger.info("Background ingestion service stopped")


def schedule_periodic_full_scan(ctx: ElroyContext) -> None:
    """Schedule periodic full directory scans.

    Args:
        ctx: The Elroy context
    """

    def full_scan_task(scan_ctx: ElroyContext) -> None:
        """Task function for scheduled full scans."""
        try:
            if should_run_full_scan(scan_ctx):
                perform_full_scan(scan_ctx)

            # Reschedule next scan
            next_scan_time = datetime.now() + timedelta(hours=scan_ctx.background_ingestion_full_scan_interval_hours)
            scheduler = get_scheduler()
            scheduler.add_job(
                lambda: full_scan_task(scan_ctx),
                "date",
                run_date=next_scan_time,
                id=f"background_full_scan_{scan_ctx.user_id}",
                replace_existing=True,
            )

        except Exception as e:
            logger.error(f"Error in scheduled full scan: {str(e)}", exc_info=True)

    # Schedule the first scan
    next_scan_time = datetime.now() + timedelta(hours=ctx.background_ingestion_full_scan_interval_hours)
    scheduler = get_scheduler()
    scheduler.add_job(
        lambda: full_scan_task(ctx), "date", run_date=next_scan_time, id=f"background_full_scan_{ctx.user_id}", replace_existing=True
    )

    logger.debug(f"Scheduled periodic full scan for user {ctx.user_id}")


def restart_background_ingestion_for_user(ctx: ElroyContext) -> bool:
    """Restart background ingestion service for a user.

    This is useful when configuration changes require a restart.

    Args:
        ctx: The Elroy context

    Returns:
        True if restarted successfully, False otherwise
    """
    global _background_service

    # Stop existing service
    if _background_service:
        _background_service.stop()
        _background_service = None

    # Remove existing scheduled tasks for this user
    scheduler = get_scheduler()
    try:
        scheduler.remove_job(f"background_full_scan_{ctx.user_id}")
    except:
        pass  # Job might not exist

    # Start fresh
    return start_background_ingestion_for_user(ctx)


def get_background_ingestion_status() -> dict:
    """Get the current status of the background ingestion service.

    Returns:
        Dictionary with service status information
    """
    global _background_service

    return {
        "service_running": _background_service is not None and _background_service.is_service_running(),
        "service_exists": _background_service is not None,
    }
