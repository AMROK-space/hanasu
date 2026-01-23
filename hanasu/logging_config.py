"""Logging configuration for Hanasu."""

import logging
import sys
from pathlib import Path

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FORMAT_SIMPLE = "[%(levelname)s] %(message)s"


def setup_logging(debug: bool = False, log_to_file: bool = True) -> logging.Logger:
    """Configure logging for the application.

    Args:
        debug: Enable DEBUG level logging.
        log_to_file: Write logs to ~/Library/Logs/Hanasu/hanasu.log

    Returns:
        Root logger for the application.
    """
    root_logger = logging.getLogger("hanasu")
    root_logger.setLevel(logging.DEBUG if debug else logging.INFO)

    # Clear existing handlers to avoid duplicates on re-initialization
    root_logger.handlers.clear()

    # Console handler (stderr)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.DEBUG if debug else logging.WARNING)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT_SIMPLE))
    root_logger.addHandler(console_handler)

    # File handler
    if log_to_file:
        log_dir = Path.home() / "Library" / "Logs" / "Hanasu"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "hanasu.log"

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        root_logger.addHandler(file_handler)

    return root_logger
