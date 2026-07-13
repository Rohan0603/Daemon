"""Tests for daemon.py — crash_dump rotation, boot helpers."""
import pathlib


def test_crash_dump_rotated_when_over_1mb(tmp_path):
    """crash_dump.log > 1MB on boot should be renamed to crash_dump.log.bak."""
    crash_log = tmp_path / "crash_dump.log"
    bak_log   = tmp_path / "crash_dump.log.bak"

    crash_log.write_bytes(b"x" * (1024 * 1024 + 1))  # 1MB + 1 byte

    from daemon import _rotate_crash_dump
    _rotate_crash_dump(crash_log)

    assert bak_log.exists()
    assert not crash_log.exists() or crash_log.stat().st_size == 0


def test_crash_dump_not_rotated_when_under_1mb(tmp_path):
    """crash_dump.log under 1MB should not be rotated."""
    crash_log = tmp_path / "crash_dump.log"
    crash_log.write_text("small log")

    from daemon import _rotate_crash_dump
    _rotate_crash_dump(crash_log)

    assert crash_log.exists()
    assert not (tmp_path / "crash_dump.log.bak").exists()


def test_crash_dump_not_rotated_when_missing(tmp_path):
    """No crash_dump.log should not raise."""
    crash_log = tmp_path / "crash_dump.log"

    from daemon import _rotate_crash_dump
    _rotate_crash_dump(crash_log)  # must not raise

    assert not crash_log.exists()


def test_probe_ollama_sets_available_true(monkeypatch):
    """When GET /api/tags returns ok=True, session is set to True."""
    from unittest.mock import MagicMock, patch
    from src import config as cfg_mod
    cfg_mod._SESSION.clear()

    mock_resp = MagicMock()
    mock_resp.ok = True

    with patch("requests.get", return_value=mock_resp) as mock_get:
        from daemon import _probe_ollama_health
        _probe_ollama_health()

    from src.config import session_get
    assert session_get("ollama_available") is True
    mock_get.assert_called_once_with("http://127.0.0.1:11434/api/tags", timeout=0.2)


def test_probe_ollama_sets_available_false_on_connection_error(monkeypatch):
    """When requests.get raises ConnectionError, session is False."""
    import requests
    from unittest.mock import patch
    from src import config as cfg_mod
    cfg_mod._SESSION.clear()

    with patch("requests.get", side_effect=requests.exceptions.ConnectionError):
        from daemon import _probe_ollama_health
        _probe_ollama_health()

    from src.config import session_get
    assert session_get("ollama_available") is False


def test_probe_ollama_sets_available_false_on_non_ok_status(monkeypatch):
    """When server responds but ok=False (e.g. 503), session is False."""
    from unittest.mock import MagicMock, patch
    from src import config as cfg_mod
    cfg_mod._SESSION.clear()

    mock_resp = MagicMock()
    mock_resp.ok = False

    with patch("requests.get", return_value=mock_resp):
        from daemon import _probe_ollama_health
        _probe_ollama_health()

    from src.config import session_get
    assert session_get("ollama_available") is False
