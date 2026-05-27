from __future__ import annotations

import logging
from typing import Any


_LOGGER_NAME = "pr_repair"


def configure_logging(level: str = "INFO") -> logging.Logger:
    """
    Configure and return the package logger.

    This module intentionally uses stdlib logging so the local-first pipeline
    works in Cursor without assuming repo-level structlog bootstrap.
    """
    logger = logging.getLogger(_LOGGER_NAME)
    if logger.handlers:
        logger.setLevel(level.upper())
        return logger

    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(level.upper())
    logger.propagate = False
    return logger


def get_logger() -> logging.Logger:
    """Return the configured pipeline logger."""
    return logging.getLogger(_LOGGER_NAME)


def log_event(event: str, **fields: Any) -> None:
    """
    Emit a structured key=value log line.

    Secrets must be masked before being passed here.
    """
    logger = get_logger()
    payload = " ".join(f"{key}={value!r}" for key, value in sorted(fields.items()))
    logger.info("%s %s", event, payload)
