import logging
import os
import sys
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler

from src.log_context import CorrelationIdDefault

_LOG_FORMAT = "[%(asctime)s] [%(levelname)-7s] [%(name)s] [cid=%(correlation_id)s] %(message)s"
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


def _add_structlog_cid(logger, method_name, event_dict):
    """Structlog processor: inject correlation_id from contextvar."""
    from src.log_context import get_correlation_id

    cid = get_correlation_id()
    if cid:
        event_dict["cid"] = cid
    return event_dict


def setup_logging(
    *,
    debug: bool = False,
    log_dir: str = "logs",
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    json_output: bool = False,
    config_overrides: dict[str, str] | None = None,
) -> None:
    """Configure logging with optional structlog JSON output.

    When json_output=True and structlog is available, configures structlog's
    JSONRenderer for stdout and uses plain-text RotatingFileHandler.
    Existing logger.info(...) calls with ``%s`` formatting work transparently.
    Falls back to plain-text format if structlog is not installed.
    """
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)
    root.handlers.clear()

    # ── Optional structlog JSON output ────────────────────────────────────
    if json_output:
        try:
            import structlog

            structlog.configure(
                processors=[
                    structlog.stdlib.filter_by_level,
                    structlog.contextvars.merge_contextvars,
                    structlog.stdlib.add_logger_name,
                    structlog.processors.add_log_level,
                    structlog.processors.TimeStamper(fmt="iso"),
                    structlog.processors.StackInfoRenderer(),
                    structlog.processors.format_exc_info,
                    _add_structlog_cid,
                    structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
                ],
                wrapper_class=structlog.stdlib.BoundLogger,
                context_class=dict,
                logger_factory=structlog.stdlib.LoggerFactory(),
                cache_logger_on_first_use=True,
            )

            # Console handler: JSON output
            json_formatter = structlog.stdlib.ProcessorFormatter(
                processor=structlog.processors.JSONRenderer()
            )
            console = logging.StreamHandler(sys.stdout)
            console.setLevel(root.level)
            console.setFormatter(json_formatter)
            root.addHandler(console)

            # File handler formatter: JSON as well (structured is the point)
            file_formatter = structlog.stdlib.ProcessorFormatter(
                processor=structlog.processors.JSONRenderer()
            )

            _add_file_handler(root, file_formatter, log_dir, max_bytes, backup_count)
            _cleanup_old_logs(log_dir)
            _apply_overrides(config_overrides)
            logging.captureWarnings(True)
            return
        except ImportError:
            json_output = False

    # ── Plain-text logging (default) ──────────────────────────────────────
    formatter = CorrelationIdDefault(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    console = logging.StreamHandler()
    console.setLevel(root.level)
    console.setFormatter(formatter)
    root.addHandler(console)

    _add_file_handler(root, formatter, log_dir, max_bytes, backup_count)
    _cleanup_old_logs(log_dir)
    _apply_overrides(config_overrides)
    logging.captureWarnings(True)


def _add_file_handler(
    root: logging.Logger,
    formatter: logging.Formatter,
    log_dir: str,
    max_bytes: int,
    backup_count: int,
) -> None:
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_path = os.path.join(log_dir, f"daemon_{timestamp}.log")
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)


def _apply_overrides(config_overrides: dict[str, str] | None) -> None:
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
