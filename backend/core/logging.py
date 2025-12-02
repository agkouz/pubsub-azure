# backend/core/logging.py

import logging
import os
import sys


DEFAULT_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def setup_logging() -> None:
    """
    Configure application-wide logging.

    - Sets root logger level (default: INFO, override with LOG_LEVEL env var)
    - Sends logs to stdout (so Azure App Service / Container picks them up)
    - Reduces noise from Azure SDK + Uvicorn access logs
    """
    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, log_level_name, logging.INFO)

    # If logging is already configured (e.g. by Uvicorn), don't re-add handlers
    root_logger = logging.getLogger()
    if root_logger.handlers:
        root_logger.setLevel(level)
        return

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(DEFAULT_FORMAT)
    handler.setFormatter(formatter)

    root_logger.setLevel(level)
    root_logger.addHandler(handler)

    # Quiet down noisy libraries
    logging.getLogger("azure.servicebus").setLevel(logging.WARNING)
    logging.getLogger("azure.servicebus._pyamqp").setLevel(logging.WARNING)
    logging.getLogger("azure.identity").setLevel(logging.WARNING)
    logging.getLogger("azure.identity.aio").setLevel(logging.WARNING)

    # Uvicorn loggers – keep error logs, tone down access chatter if you like
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)


def get_logger(name: str | None = None) -> logging.Logger:
    """
    Helper to get a logger with our app's configuration applied.

    Usage:
        from backend.core.logging import get_logger

        logger = get_logger(__name__)
        logger.info("Hello from my module")
    """
    return logging.getLogger(name)
