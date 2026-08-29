import logging
import os
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).parent.parent.parent.resolve())
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
logger = logging.getLogger(__name__)


def is_safe_write_path(requested_path: str) -> bool:
    try:
        abs_requested = os.path.abspath(requested_path)
        abs_data = os.path.abspath(DATA_DIR)
        if not abs_requested.startswith(abs_data):
            logger.warning("Rejected write path outside data directory: %s", requested_path)
            return False
        real_requested = os.path.realpath(abs_requested)
        real_data = os.path.realpath(abs_data)
        if not real_requested.startswith(real_data):
            logger.warning("Rejected write path through symlink: %s", requested_path)
            return False
        return True
    except Exception:
        logger.exception("Failed to validate write path: %s", requested_path)
        return False


def get_safe_data_path(relative_path: str) -> str:
    abs_path = os.path.abspath(os.path.join(DATA_DIR, relative_path))
    if not is_safe_write_path(abs_path):
        raise ValueError(f"Path escapes data directory: {relative_path}")
    return abs_path
