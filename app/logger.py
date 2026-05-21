"""Logging centralisé — TAC MP4 Studio."""
from __future__ import annotations

import logging
import os
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.errors import TACError

_LOG_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / "DoktorP3st" / "TAC_MP4" / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_LOG_FILE = _LOG_DIR / "tac.log"

_root = logging.getLogger("tac")
_root.setLevel(logging.DEBUG)

if not _root.handlers:
    _file_handler = RotatingFileHandler(
        _LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    _file_handler.setLevel(logging.DEBUG)
    _file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s — %(message)s")
    )
    _root.addHandler(_file_handler)

    _console_handler = logging.StreamHandler()
    _console_handler.setLevel(logging.WARNING)
    _console_handler.setFormatter(
        logging.Formatter("[%(levelname)s] %(name)s — %(message)s")
    )
    _root.addHandler(_console_handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"tac.{name}")


def log_exception(exc: Exception, context: str = "") -> None:
    logger = get_logger("exception")
    user_msg = exc.message if isinstance(exc, TACError) else str(exc)
    detail = exc.detail if isinstance(exc, TACError) else ""
    tb = traceback.format_exc()

    parts = []
    if context:
        parts.append(f"Context: {context}")
    parts.append(f"User message: {user_msg}")
    if detail:
        parts.append(f"Detail: {detail}")
    parts.append(f"Traceback:\n{tb}")

    logger.error("\n".join(parts))
