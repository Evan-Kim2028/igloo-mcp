"""Logging configuration for the lineage module."""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional


def setup_logging(
    level: str = "INFO",
    log_file: Optional[Path] = None,
    format_string: Optional[str] = None,
    enable_color: bool = True,
) -> None:
    """
    Set up logging configuration for the lineage module.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file
        format_string: Optional custom format string
        enable_color: Enable colored output for console
    """
    # Default format
    if not format_string:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Create formatter
    formatter = logging.Formatter(format_string)

    # Get root logger for the lineage module
    logger = logging.getLogger("nanuk_mcp.lineage")
    logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    logger.handlers = []

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper()))

    if enable_color and sys.stdout.isatty():
        console_handler.setFormatter(ColoredFormatter(format_string))
    else:
        console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)

    # File handler if specified
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
        )
        file_handler.setLevel(getattr(logging, level.upper()))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)


class ColoredFormatter(logging.Formatter):
    """Formatter that adds colors to log levels."""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record with color."""
        log_color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{log_color}{record.levelname}{self.RESET}"
        return super().format(record)


class LoggingContext:
    """Context manager for temporary logging configuration."""

    def __init__(self, level: str = "INFO", suppress: bool = False):
        self.level = level
        self.suppress = suppress
        self.original_level = None
        self.logger = logging.getLogger("nanuk_mcp.lineage")

    def __enter__(self):
        """Enter the context and modify logging."""
        self.original_level = self.logger.level
        if self.suppress:
            self.logger.setLevel(logging.CRITICAL + 1)
        else:
            self.logger.setLevel(getattr(logging, self.level.upper()))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context and restore logging."""
        self.logger.setLevel(self.original_level)
        return False


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for the given name."""
    return logging.getLogger(f"nanuk_mcp.lineage.{name}")


# Module-specific loggers
def get_extractor_logger() -> logging.Logger:
    """Get logger for extractors."""
    return get_logger("extractor")


def get_analyzer_logger() -> logging.Logger:
    """Get logger for analyzers."""
    return get_logger("analyzer")


def get_builder_logger() -> logging.Logger:
    """Get logger for builders."""
    return get_logger("builder")


def get_parser_logger() -> logging.Logger:
    """Get logger for parsers."""
    return get_logger("parser")


def get_storage_logger() -> logging.Logger:
    """Get logger for storage operations."""
    return get_logger("storage")


def log_operation(operation: str, **kwargs):
    """Decorator to log operation execution."""

    def decorator(func):
        def wrapper(*args, **func_kwargs):
            logger = get_logger(func.__module__.split(".")[-1])
            logger.debug(f"Starting {operation}", extra=kwargs)
            try:
                result = func(*args, **func_kwargs)
                logger.debug(f"Completed {operation}", extra=kwargs)
                return result
            except Exception as e:
                logger.error(
                    f"Failed {operation}: {str(e)}",
                    exc_info=True,
                    extra=kwargs,
                )
                raise

        return wrapper

    return decorator


def log_performance(operation: str):
    """Decorator to log operation performance."""
    import time

    def decorator(func):
        def wrapper(*args, **kwargs):
            logger = get_logger(func.__module__.split(".")[-1])
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start_time
                logger.debug(
                    f"{operation} completed in {elapsed:.3f}s",
                    extra={"elapsed": elapsed, "operation": operation},
                )
                return result
            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(
                    f"{operation} failed after {elapsed:.3f}s: {str(e)}",
                    extra={"elapsed": elapsed, "operation": operation},
                )
                raise

        return wrapper

    return decorator
