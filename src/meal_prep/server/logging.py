"""Operational file logging for the diary web server.

Meal data lives in YAML week files; this module is plain application logging
(requests handled, validation failures, tracebacks) so server errors can be
diagnosed after the fact.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOGGER_NAME = "meal_prep.server"
_LOG_FILE_NAME = "diary-server.log"
_MAX_BYTES = 1_000_000
_BACKUP_COUNT = 5

_configured_files: set[Path] = set()
_console_configured = False


def configure_logging(log_dir: Path | None, level: str = "INFO") -> Path | None:
    """Route server logs to ``<log_dir>/diary-server.log`` (rotating) + stdout.

    Safe to call repeatedly: each log file gets exactly one handler.
    Returns the log file path, or ``None`` when ``log_dir`` is ``None``.
    """
    global _console_configured
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level.upper())
    if not _console_configured:
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        logger.addHandler(console)
        _console_configured = True
    if log_dir is None:
        return None
    log_file = Path(log_dir) / _LOG_FILE_NAME
    if log_file in _configured_files:
        return log_file
    log_file.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_file, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s")
    )
    logger.addHandler(handler)
    _configured_files.add(log_file)
    return log_file
