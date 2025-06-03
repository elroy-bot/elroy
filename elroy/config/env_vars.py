# Params set by env variables rather than the command line or config

import logging
import os


def is_tracing_enabled() -> bool:
    return os.environ.get("ELROY_ENABLE_TRACING", "").lower() in ("1", "true", "yes")


def get_log_level() -> int:
    log_level = os.environ.get("ELROY_LOG_LEVEL", "WARNING").upper()

    if log_level == "INFO":
        return logging.INFO
    elif log_level == "DEBUG":
        return logging.DEBUG
    elif log_level == "ERROR":
        return logging.ERROR
    elif log_level in ("WARNING", "WARN"):
        return logging.WARNING
    elif log_level == "CRITICAL":
        return logging.CRITICAL
    else:
        return logging.INFO
