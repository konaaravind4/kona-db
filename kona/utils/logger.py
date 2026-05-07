"""
KonaDB Logging Utility

Provides configurable logging with colored output for the CLI and
optional file handler support.
"""

import logging
import sys


# ANSI color codes for terminal output
COLORS = {
    "DEBUG": "\033[36m",     # Cyan
    "INFO": "\033[32m",      # Green
    "WARNING": "\033[33m",   # Yellow
    "ERROR": "\033[31m",     # Red
    "CRITICAL": "\033[41m",  # Red background
    "RESET": "\033[0m",
}


class ColoredFormatter(logging.Formatter):
    """Formatter that adds ANSI color codes based on log level."""

    def __init__(self, fmt=None, datefmt=None, use_color=True):
        super().__init__(fmt, datefmt)
        self.use_color = use_color

    def format(self, record):
        if self.use_color and record.levelname in COLORS:
            color = COLORS[record.levelname]
            reset = COLORS["RESET"]
            record.levelname = f"{color}{record.levelname}{reset}"
            record.msg = f"{color}{record.msg}{reset}"
        return super().format(record)


def get_logger(name="kona", level=logging.INFO, log_file=None, use_color=True):
    """
    Get or create a KonaDB logger.

    Args:
        name: Logger name (default: 'kona')
        level: Logging level (default: INFO)
        log_file: Optional file path for log output
        use_color: Whether to use ANSI colors in console output

    Returns:
        Configured logging.Logger instance
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers
    if logger.handlers:
        return logger

    logger.setLevel(level)
    logger.propagate = False

    # Console handler with colored output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_fmt = ColoredFormatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        use_color=use_color,
    )
    console_handler.setFormatter(console_fmt)
    logger.addHandler(console_handler)

    # Optional file handler (no colors)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_fmt = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_fmt)
        logger.addHandler(file_handler)

    return logger
