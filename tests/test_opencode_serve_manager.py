"""Tests for opencode_serve_manager.

The manager ensures `opencode serve --port 4096` is running before the daemon
attempts API calls. If the port is already bound, it does nothing. Otherwise
it spawns a detached background process and waits for it to bind.
"""
import sys
import os
import pytest
from unittest.mock import patch, MagicMock


class FakeCompletedProcess:
    def __init__(self, stdout: str = "", returncode: int = 0):
        self.stdout = stdout
        self.returncode = returncode


def test_port_already_bound_returns_true_without_spawn(tmp_path):
    """If port 4096 is already accepting connections, don't spawn anything."""
    from src.opencode_serve_manager import ensure_opencode_serve_running

    fake_sock = MagicMock()
    fake_sock.__enter__ = MagicMock(return_value=fake_sock)
    fake_sock.__exit__ = MagicMock(return_value=False)
    with patch("src.opencode_serve_manager.socket.create_connection",
               return_value=fake_sock) as cc, \
         patch("src.opencode_serve_manager.subprocess.Popen") as popen:
        result = ensure_opencode_serve_running(
            url="http://127.0.0.1:4096",
            max_wait=1.0,
            spawn_log_path=str(tmp_path / "serve.log"),
        )
    assert result is True
    cc.assert_called_once_with(("127.0.0.1", 4096), timeout=0.5)
    popen.assert_not_called()


def test_port_closed_spawns_opencode_serve(tmp_path):
    """If the port is closed, locate opencode on PATH and spawn it."""
    from src.opencode_serve_manager import ensure_opencode_serve_running

    fake_sock = MagicMock()
    fake_sock.__enter__ = MagicMock(return_value=fake_sock)
    fake_sock.__exit__ = MagicMock(return_value=False)

    popen_mock = MagicMock()
    popen_mock.poll.return_value = None  # process still running

    call_count = {"n": 0}

    def _connect(addr, *args, **kwargs):
        # First call (port check before spawn) raises; subsequent calls (post-spawn)
        # succeed so the function returns True
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise OSError("connection refused")
        return fake_sock

    with patch("src.opencode_serve_manager.socket.create_connection",
               side_effect=_connect), \
         patch("src.opencode_serve_manager.shutil.which",
               return_value="C:/fake/opencode.exe"), \
         patch("src.opencode_serve_manager.subprocess.Popen",
               return_value=popen_mock) as popen:
        result = ensure_opencode_serve_running(
            url="http://127.0.0.1:4096",
            max_wait=2.0,
            spawn_log_path=str(tmp_path / "serve.log"),
        )
    assert result is True
    popen.assert_called_once()
    args, kwargs = popen.call_args
    cmd = args[0]
    assert cmd[0] == "C:/fake/opencode.exe"
    assert "serve" in cmd
    assert "--port" in cmd
    assert "4096" in cmd
    # stdout must be redirected so the child doesn't hold a handle
    assert "stdout" in kwargs
    assert "stderr" in kwargs
    assert "stdin" in kwargs
    # detached so it survives parent exit
    assert "creationflags" in kwargs
    flags = kwargs["creationflags"]
    assert flags & 0x00000008  # DETACHED_PROCESS
    assert flags & 0x08000000  # CREATE_NO_WINDOW


def test_opencode_not_in_path_returns_false(tmp_path):
    """If opencode is not on PATH, return False and don't crash."""
    from src.opencode_serve_manager import ensure_opencode_serve_running

    with patch("src.opencode_serve_manager.socket.create_connection",
               side_effect=OSError("refused")), \
         patch("src.opencode_serve_manager.shutil.which", return_value=None):
        result = ensure_opencode_serve_running(
            url="http://127.0.0.1:4096",
            max_wait=1.0,
            spawn_log_path=str(tmp_path / "serve.log"),
        )
    assert result is False


def test_popen_raises_returns_false(tmp_path):
    """If Popen itself fails (e.g. binary not executable), return False."""
    from src.opencode_serve_manager import ensure_opencode_serve_running

    with patch("src.opencode_serve_manager.socket.create_connection",
               side_effect=OSError("refused")), \
         patch("src.opencode_serve_manager.shutil.which",
               return_value="C:/fake/opencode.exe"), \
         patch("src.opencode_serve_manager.subprocess.Popen",
               side_effect=OSError("not executable")):
        result = ensure_opencode_serve_running(
            url="http://127.0.0.1:4096",
            max_wait=1.0,
            spawn_log_path=str(tmp_path / "serve.log"),
        )
    assert result is False


def test_does_not_block_longer_than_max_wait(tmp_path):
    """If the spawned server never binds, return False after max_wait seconds."""
    from src.opencode_serve_manager import ensure_opencode_serve_running
    import time

    popen_mock = MagicMock()
    popen_mock.poll.return_value = None

    # Always raise so the bind check never succeeds
    with patch("src.opencode_serve_manager.socket.create_connection",
               side_effect=OSError("never binds")), \
         patch("src.opencode_serve_manager.shutil.which",
               return_value="C:/fake/opencode.exe"), \
         patch("src.opencode_serve_manager.subprocess.Popen",
               return_value=popen_mock), \
         patch("src.opencode_serve_manager.time.monotonic") as mock_time:
        # Simulate clock advancing past max_wait on every call
        mock_time.side_effect = [0.0, 0.0, 0.0, 0.0, 0.0, 100.0, 100.0, 100.0, 100.0]
        t0 = time.monotonic()
        result = ensure_opencode_serve_running(
            url="http://127.0.0.1:4096",
            max_wait=2.0,
            spawn_log_path=str(tmp_path / "serve.log"),
        )
    assert result is False


def test_url_with_custom_port_parses_correctly(tmp_path):
    """Port is parsed from the URL, not hardcoded to 4096."""
    from src.opencode_serve_manager import ensure_opencode_serve_running

    fake_sock = MagicMock()
    fake_sock.__enter__ = MagicMock(return_value=fake_sock)
    fake_sock.__exit__ = MagicMock(return_value=False)
    with patch("src.opencode_serve_manager.socket.create_connection",
               return_value=fake_sock) as cc, \
         patch("src.opencode_serve_manager.subprocess.Popen") as popen:
        result = ensure_opencode_serve_running(
            url="http://127.0.0.1:9999",
            max_wait=1.0,
            spawn_log_path=str(tmp_path / "serve.log"),
        )
    assert result is True
    cc.assert_called_once_with(("127.0.0.1", 9999), timeout=0.5)


def test_spawn_log_path_creates_parent_dir(tmp_path):
    """Log file's parent directory is created if it doesn't exist."""
    from src.opencode_serve_manager import ensure_opencode_serve_running

    log_path = str(tmp_path / "subdir" / "serve.log")
    fake_sock = MagicMock()
    fake_sock.__enter__ = MagicMock(return_value=fake_sock)
    fake_sock.__exit__ = MagicMock(return_value=False)

    call_count = {"n": 0}

    def _connect(addr, *args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise OSError("refused")
        return fake_sock

    popen_mock = MagicMock()
    popen_mock.poll.return_value = None
    with patch("src.opencode_serve_manager.socket.create_connection",
               side_effect=_connect), \
         patch("src.opencode_serve_manager.shutil.which",
               return_value="C:/fake/opencode.exe"), \
         patch("src.opencode_serve_manager.subprocess.Popen",
               return_value=popen_mock):
        result = ensure_opencode_serve_running(
            url="http://127.0.0.1:4096",
            max_wait=2.0,
            spawn_log_path=log_path,
        )
    assert result is True
    assert os.path.isdir(str(tmp_path / "subdir"))


def test_no_spawn_when_already_running_even_if_max_wait_small(tmp_path):
    """Early return path must not wait at all when port is bound."""
    from src.opencode_serve_manager import ensure_opencode_serve_running

    fake_sock = MagicMock()
    fake_sock.__enter__ = MagicMock(return_value=fake_sock)
    fake_sock.__exit__ = MagicMock(return_value=False)
    with patch("src.opencode_serve_manager.socket.create_connection",
               return_value=fake_sock), \
         patch("src.opencode_serve_manager.subprocess.Popen") as popen, \
         patch("src.opencode_serve_manager.time.monotonic") as clock:
        result = ensure_opencode_serve_running(
            url="http://127.0.0.1:4096",
            max_wait=10.0,  # large
            spawn_log_path=str(tmp_path / "serve.log"),
        )
    assert result is True
    # We never even queried the clock because we returned early
    clock.assert_not_called()


def test_stop_opencode_serve_kills_tracked_pid(monkeypatch):
    import src.opencode_serve_manager as osm
    osm._SERVE_PID = 12345
    killed_pid = [None]

    def mock_run(cmd, **kw):
        if "taskkill" in str(cmd):
            killed_pid[0] = cmd[3] if len(cmd) > 3 else None
        return FakeCompletedProcess(stdout="", returncode=0)

    monkeypatch.setattr("subprocess.run", mock_run)
    osm.stop_opencode_serve()
    assert killed_pid[0] == "12345"
    assert osm._SERVE_PID is None


def test_stop_opencode_serve_noop_when_no_pid(monkeypatch):
    import src.opencode_serve_manager as osm
    osm._SERVE_PID = None
    called = [False]

    def mock_run(cmd, **kw):
        called[0] = True
        return FakeCompletedProcess(stdout="", returncode=0)

    monkeypatch.setattr("subprocess.run", mock_run)
    osm.stop_opencode_serve()
    assert not called[0]
