import logging
import os
import pytest
from src.logging_setup import setup_logging


@pytest.fixture(autouse=True)
def reset_logging():
    root = logging.getLogger()
    root.handlers.clear()
    yield


def test_setup_logging_creates_log_dir(tmp_path):
    log_dir = str(tmp_path / "logs")
    setup_logging(debug=True, log_dir=log_dir)
    assert os.path.isdir(log_dir)


def test_setup_logging_sets_root_level_debug(tmp_path):
    setup_logging(debug=True, log_dir=str(tmp_path))
    assert logging.getLogger().level == logging.DEBUG


def test_setup_logging_sets_root_level_info(tmp_path):
    setup_logging(debug=False, log_dir=str(tmp_path))
    assert logging.getLogger().level == logging.INFO


def test_setup_logging_applies_module_overrides(tmp_path):
    setup_logging(debug=True, log_dir=str(tmp_path), config_overrides={"test_module_foo": "WARNING"})
    test_logger = logging.getLogger("test_module_foo")
    assert test_logger.level == logging.WARNING


def test_setup_logging_file_handler_present(tmp_path):
    setup_logging(debug=True, log_dir=str(tmp_path))
    root = logging.getLogger()
    file_handlers = [h for h in root.handlers if isinstance(h, logging.FileHandler)]
    assert len(file_handlers) == 1
    assert file_handlers[0].level == logging.DEBUG


def test_log_file_is_timestamped(tmp_path):
    setup_logging(debug=True, log_dir=str(tmp_path))
    log_files = [f for f in os.listdir(str(tmp_path)) if f.startswith("daemon_") and f.endswith(".log")]
    assert len(log_files) == 1
    assert log_files[0] != "daemon.log"


def test_cleanup_removes_old_logs(tmp_path):
    from src.logging_setup import _cleanup_old_logs
    import time

    old = os.path.join(str(tmp_path), "daemon_2020-01-01_00-00-00.log")
    new = os.path.join(str(tmp_path), "daemon_2026-06-08_00-00-00.log")
    with open(old, "w") as f:
        f.write("old")
    with open(new, "w") as f:
        f.write("new")
    old_mtime = time.time() - 20 * 86400
    os.utime(old, (old_mtime, old_mtime))
    _cleanup_old_logs(str(tmp_path), days=7)
    assert not os.path.exists(old)
    assert os.path.exists(new)
