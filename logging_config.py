"""
logging_config.py
One-call logging setup that writes to app.log (rotating) and to the console.
Import setup_logging() from any module; it's idempotent, so importing it
from every entry point is safe.

Log format:
  [YYYY-MM-DD HH:MM:SS.mmm] LEVEL   module.name: message

Verbosity is controlled by the LOG_LEVEL env var (default INFO). Set
LOG_LEVEL=DEBUG to see request bodies, per-question answers, etc.
"""

import logging
import logging.handlers
import os
from pathlib import Path

LOG_FILE = Path(__file__).with_name("app.log")
MAX_BYTES = 5 * 1024 * 1024   # 5 MB per file
BACKUP_COUNT = 3              # keep the last 3 rotations

_INITIALIZED = False


def setup_logging(level: str | None = None) -> None:
    """Configure the root logger. Safe to call more than once."""
    global _INITIALIZED
    if _INITIALIZED:
        return

    level_name = (level or os.environ.get("LOG_LEVEL") or "INFO").upper()
    log_level = getattr(logging, level_name, logging.INFO)

    fmt = logging.Formatter(
        fmt="[%(asctime)s.%(msecs)03d] %(levelname)-7s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    file_handler.setLevel(log_level)

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    # Console stays at WARNING by default so it doesn't drown the CLI/Streamlit
    # output; set LOG_LEVEL to also open up the console.
    console.setLevel(log_level if level_name in {"DEBUG", "WARNING", "ERROR"} else logging.WARNING)

    root = logging.getLogger()
    # Wipe pre-existing handlers so re-imports don't stack duplicates.
    for h in list(root.handlers):
        root.removeHandler(h)
    root.setLevel(log_level)
    root.addHandler(file_handler)
    root.addHandler(console)

    # Tame verbose third-party loggers.
    for noisy in ("httpx", "httpx2", "httpcore", "anthropic", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger("logging_config").info(
        "logging initialised level=%s file=%s", level_name, LOG_FILE,
    )
    _INITIALIZED = True