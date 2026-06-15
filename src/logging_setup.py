import logging
import os
import time
from datetime import datetime

_LOG_FORMAT = "[%(asctime)s] [%(levelname)-7s] [%(name)s] %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _cleanup_old_logs(log_dir: str, days: int = 7) -> None:
    cutoff = time.time() - days * 86400
    for fname in os.listdir(log_dir):
        if fname.startswith("daemon_") and fname.endswith(".log"):
            fpath = os.path.join(log_dir, fname)
            try:
                if os.path.getmtime(fpath) < cutoff:
                    os.remove(fpath)
            except OSError:
                pass


def setup_logging(
    *,
    debug: bool = False,
    log_dir: str = "logs",
    config_overrides: dict[str, str] | None = None,
) -> None:
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    console = logging.StreamHandler()
    console.setLevel(root.level)
    console.setFormatter(formatter)
    root.addHandler(console)

    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_path = os.path.join(log_dir, f"daemon_{timestamp}.log")
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)
    _cleanup_old_logs(log_dir)

    default_overrides = {
        "comtypes": "WARNING",
        "comtypes.client": "WARNING",
        "comtypes.client._code_cache": "WARNING",
        "comtypes.client._generate": "WARNING",
        "comtypes._post_coinit": "WARNING",
        "urllib3.connectionpool": "WARNING",
    }
    if config_overrides:
        default_overrides.update(config_overrides)
    for name, level in default_overrides.items():
        if not isinstance(level, str):
            continue
        logging.getLogger(name).setLevel(getattr(logging, level.upper(), logging.INFO))

    logging.captureWarnings(True)
