"""Background lifecycle for `opencode serve`.

The daemon prefers the OpenCode HTTP API when available, but the API requires
a separate `opencode serve` process bound to port 4096. The TUI does not serve —
they are different processes. To make the API path "just work", the daemon
auto-spawns the server on startup if the port is not already bound.
"""
import os
import shutil
import socket
import subprocess
import time
from typing import Optional
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)

_SERVE_PID: int | None = None

# Win32 creation flags — must be set so the child is detached and has no console
_DETACHED_PROCESS = 0x00000008
_CREATE_NO_WINDOW = 0x08000000

# Reasonable defaults; override via kwargs for tests
_DEFAULT_URL = "http://127.0.0.1:4096"
_DEFAULT_MAX_WAIT_SEC = 5.0
_DEFAULT_POLL_INTERVAL_SEC = 0.1
_DEFAULT_BIND_CHECK_TIMEOUT_SEC = 0.5
_DEFAULT_LOG_PATH = os.path.join(
    os.environ.get("TEMP", os.environ.get("TMP", "/tmp")),
    "opencode-serve.log",
)


def _parse_host_port(url: str) -> tuple[str, int]:
    """Extract (host, port) from a URL like http://127.0.0.1:4096/."""
    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 4096
    return host, port


def _is_port_bound(host: str, port: int, timeout: float) -> bool:
    """Return True if a TCP connect to (host, port) succeeds within timeout."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _kill_process_on_port(host: str, port: int) -> bool:
    """Kill any process listening on host:port using netstat + taskkill.

    Returns True if at least one process was killed, False otherwise.
    Never raises.
    """
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True, timeout=5,
            creationflags=_CREATE_NO_WINDOW,
        )
        listen_str = f"{host}:{port}"
        killed = False
        for line in result.stdout.splitlines():
            if listen_str in line and "LISTENING" in line:
                parts = line.split()
                pid = parts[-1]
                subprocess.run(
                    ["taskkill", "/F", "/PID", pid],
                    capture_output=True, timeout=5,
                    creationflags=_CREATE_NO_WINDOW,
                )
                logger.debug("[serve] killed PID %s on port %d", pid, port)
                killed = True
        return killed
    except Exception as e:
        logger.debug("[serve] _kill_process_on_port failed: %s", e)
        return False


def ensure_opencode_serve_running(
    url: str = _DEFAULT_URL,
    max_wait: float = _DEFAULT_MAX_WAIT_SEC,
    spawn_log_path: Optional[str] = None,
    api_key: str = "",
    which=None,
    popen=None,
) -> bool:
    """Ensure `opencode serve --port <port>` is running with a FRESH server.

    If the port is already bound, kills the existing process and spawns a new
    server so that updated configs (SKILL.md, opencode.json) are always loaded.

    Returns True if the port is bound after the attempt. Returns False if the
    server could not be started (binary not on PATH, spawn failed, or it never
    bound within `max_wait`).

    Never raises. Designed to be called at daemon startup.
    """
    spawn_log_path = spawn_log_path or _DEFAULT_LOG_PATH
    if which is None:
        which = shutil.which
    if popen is None:
        popen = subprocess.Popen

    host, port = _parse_host_port(url)

    # If something is already bound, kill it so we can spawn a fresh server
    if _is_port_bound(host, port, _DEFAULT_BIND_CHECK_TIMEOUT_SEC):
        bin_path = which("opencode")
        if bin_path:
            logger.debug("[serve] port %d already bound; killing to respawn fresh", port)
            _kill_process_on_port(host, port)
            time.sleep(0.5)
            if _is_port_bound(host, port, _DEFAULT_BIND_CHECK_TIMEOUT_SEC):
                logger.debug("[serve] port %d still bound after kill; reusing existing", port)
                return True
        else:
            logger.debug("[serve] port %d already bound; opencode not on PATH, reusing", port)
            return True

    # Port is free; try to find opencode on PATH
    bin_path = which("opencode")
    if not bin_path:
        logger.debug("[serve] opencode not on PATH; skipping auto-spawn (port %d)", port)
        return False

    # Make sure the log directory exists
    log_dir = os.path.dirname(spawn_log_path)
    if log_dir:
        try:
            os.makedirs(log_dir, exist_ok=True)
        except OSError as e:
            logger.debug(f"[serve] could not create log dir {log_dir}: {e}")
            return False

    logger.debug(f"[serve] spawning {bin_path} serve --port {port}")
    try:
        env = os.environ.copy()
        if api_key:
            env["OPENCODE_API_KEY"] = api_key
            env["GEMINI_API_KEY"] = api_key  # Some providers fallback to this
        log_file = open(spawn_log_path, "ab", buffering=0)
        proc = popen(
            [bin_path, "serve", "--port", str(port), "--print-logs", "--log-level", "DEBUG"],
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=log_file,
            env=env,
            creationflags=_CREATE_NO_WINDOW,
            close_fds=True,
            start_new_session=True,
        )
    except OSError as e:
        logger.debug(f"[serve] spawn failed: {e}")
        return False

    global _SERVE_PID
    _SERVE_PID = proc.pid

    # Wait up to max_wait for the server to bind
    deadline = time.monotonic() + max_wait
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            logger.debug(f"[serve] child exited early with code {proc.returncode}")
            return False
        if _is_port_bound(host, port, _DEFAULT_BIND_CHECK_TIMEOUT_SEC):
            logger.debug(f"[serve] bound to {host}:{port} (pid {proc.pid})")
            return True
        time.sleep(_DEFAULT_POLL_INTERVAL_SEC)

    logger.debug(f"[serve] did not bind within {max_wait}s; giving up")
    return False


def stop_opencode_serve() -> None:
    """Kill the tracked opencode serve process if it was spawned by us."""
    global _SERVE_PID
    if _SERVE_PID is None:
        return
    try:
        subprocess.run(
            ["taskkill", "/F", "/PID", str(_SERVE_PID)],
            capture_output=True, timeout=5,
            creationflags=_CREATE_NO_WINDOW,
        )
        logger.info("Killed opencode serve (PID %d)", _SERVE_PID)
    except Exception as e:
        logger.debug("stop_opencode_serve failed: %s", e)
    finally:
        _SERVE_PID = None


def check_health(port: int = 4096, timeout: float = 1.0) -> bool:
    """Return True if the opencode serve port is accepting TCP connections.

    Uses socket.create_connection (same as _is_port_bound) to check whether
    the server process is alive. Returns False on any connection failure.
    Never raises.
    """
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False
