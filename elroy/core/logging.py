import logging
import os
import warnings
from typing import Optional

from ..config.paths import get_log_file_path

logger = logging.getLogger("elroy")


def setup_core_logging(level: int = logging.INFO):
    """Setup basic logging configuration for the Elroy library"""
    # Configure the main Elroy logger
    logger.setLevel(level)

    # Add a basic StreamHandler if no handlers exist
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(name)s - %(levelname)s - %(message)s"))
        logger.addHandler(handler)

    # Silence noisy third-party loggers
    warnings.filterwarnings("ignore", message="Valid config keys have changed in V2")
    for name in ["openai", "httpx"]:
        logging.getLogger(name).setLevel(logging.WARNING)

    # Handle litellm logging
    import litellm

    litellm.set_verbose = False  # noqa F841 # type: ignore
    litellm.suppress_debug_info = True  # noqa F841
    litellm.verbose_logger.setLevel(logging.WARNING)  # type: ignore


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a logger that is a child of the main Elroy logger.

    Args:
        name: Optional suffix for the logger name. Will be appended as elroy.{name}

    Returns:
        logging.Logger: Configured logger instance
    """
    if name:
        return logging.getLogger(f"elroy.{name}")
    return logger


def setup_file_logging():
    """Add rotating file handler to the Elroy logger - used by CLI"""

    from logging.handlers import RotatingFileHandler

    log_file_path = get_log_file_path()
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

    file_handler = RotatingFileHandler(log_file_path, maxBytes=10 * 1024 * 1024, backupCount=5)  # 10MB
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

    # Add handler to main Elroy logger
    for handler in logger.handlers:
        logger.removeHandler(handler)
    logger.addHandler(file_handler)
