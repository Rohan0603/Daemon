import os

PROJECT_ROOT = os.path.abspath("C:/Users/ponna/Project/Daemon")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")


def is_safe_write_path(requested_path: str) -> bool:
    try:
        abs_requested = os.path.abspath(requested_path)
        abs_data = os.path.abspath(DATA_DIR)
        if not abs_requested.startswith(abs_data):
            return False
        real_requested = os.path.realpath(abs_requested)
        real_data = os.path.realpath(abs_data)
        if not real_requested.startswith(real_data):
            return False
        return True
    except Exception:
        return False


def get_safe_data_path(relative_path: str) -> str:
    abs_path = os.path.abspath(os.path.join(DATA_DIR, relative_path))
    if not is_safe_write_path(abs_path):
        raise ValueError(f"Path escapes data directory: {relative_path}")
    return abs_path
