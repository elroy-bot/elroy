from typing import Optional

from sqlmodel import select

from ...core.ctx import ElroyContext
from ...db.db_models import BackgroundIngestionConfig


def get_background_ingestion_config(ctx: ElroyContext) -> Optional[BackgroundIngestionConfig]:
    """Get the background ingestion configuration for the current user.

    Args:
        ctx: The Elroy context

    Returns:
        The background ingestion configuration, or None if not configured
    """
    return ctx.db.exec(select(BackgroundIngestionConfig).where(BackgroundIngestionConfig.user_id == ctx.user_id)).first()


def get_active_background_ingestion_config(ctx: ElroyContext) -> Optional[BackgroundIngestionConfig]:
    """Get the active background ingestion configuration for the current user.

    Args:
        ctx: The Elroy context

    Returns:
        The active background ingestion configuration, or None if not configured or inactive
    """
    return ctx.db.exec(
        select(BackgroundIngestionConfig).where(
            BackgroundIngestionConfig.user_id == ctx.user_id, BackgroundIngestionConfig.is_active == True
        )
    ).first()
