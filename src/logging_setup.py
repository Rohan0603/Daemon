import logging
import os
from logging.handlers import RotatingFileHandler

_LOG_FORMAT = "[%(asctime)s] [%(levelname)-7s] [%(name)s] %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


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
    log_path = os.path.join(log_dir, "daemon.log")
    file_handler = RotatingFileHandler(
        log_path, maxBytes=1_048_576, backupCount=3
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    if config_overrides:
        for name, level in config_overrides.items():
            logging.getLogger(name).setLevel(getattr(logging, level.upper(), logging.INFO))

    logging.captureWarnings(True)
