"""Centralized logging setup for Wind Vane MCP.

Call setup_logging() once at server/notifier startup.

Design rules (spec §13.2):
  - stdlib logging  → file only (server.log)
  - structlog       → stderr  (human-readable, IDE-friendly)
  - stdout          → NEVER used  (reserved for MCP stdio protocol)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path


def log_dir() -> Path:
    """Return platform-appropriate log directory, creating it if needed."""
    if sys.platform == "win32":
        base = Path.home() / "AppData" / "Local"
    else:
        base = Path.home() / ".local" / "share"
    d = base / "wind-vane-mcp" / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def setup_logging(level: int = logging.INFO) -> Path:
    """Configure stdlib logging to file and structlog to stderr.

    Returns the path to the log file.
    """
    import structlog

    ldir = log_dir()
    log_file = ldir / "server.log"

    # stdlib → rotating file handler, never stdout
    file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-8s %(name)s  %(message)s")
    )
    root = logging.getLogger()
    root.setLevel(level)
    # Only add if not already configured (idempotent for tests)
    if not any(isinstance(h, logging.FileHandler) for h in root.handlers):
        root.addHandler(file_handler)

    # structlog → stderr (ConsoleRenderer for human readability)
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        wrapper_class=structlog.BoundLogger,
        cache_logger_on_first_use=True,
    )

    return log_file
