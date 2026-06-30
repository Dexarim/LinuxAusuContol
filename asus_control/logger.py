"""Logging setup for asus-control."""

from __future__ import annotations

import logging
from pathlib import Path


LOG_DIR = Path.home() / ".local" / "share" / "asus-control" / "logs"
LOG_FILE = LOG_DIR / "asus-control.log"
FALLBACK_LOG_DIR = Path("/tmp") / "asus-control" / "logs"


def setup_logging(name: str = "asus-control", log_dir: Path | str | None = None) -> logging.Logger:
    """Configure standard logging for CLI and daemon."""
    resolved_dir = Path(log_dir) if log_dir else LOG_DIR
    try:
        resolved_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        resolved_dir = FALLBACK_LOG_DIR
        resolved_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(resolved_dir / LOG_FILE.name, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger
