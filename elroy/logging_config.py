import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logging(log_file_path: str):
    # Create the directory for the log file if it doesn't exist
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

    # Remove all existing handlers from the root logger
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    # Configure the root logger
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[RotatingFileHandler(log_file_path, maxBytes=10 * 1024 * 1024, backupCount=5)],  # 10MB
    )

    # Silence some noisy loggers
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # Disable propagation to the root logger for all loggers
    for name in logging.root.manager.loggerDict:
        logging.getLogger(name).propagate = False
