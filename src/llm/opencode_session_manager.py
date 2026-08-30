"""Bounded lifecycle manager for reusable interactive OpenCode sessions."""
from __future__ import annotations

import logging
import os
import threading
import time
import requests

from src.config import DEFAULT_SERVER_URL

logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class OpenCodeSessionManager:
    """Own one bounded, reusable OpenCode session for interactive prompts.

    Autonomous and refill workers never use this manager.  State is process
    local; OpenCode remains the source of truth for conversation contents.
    """

    def __init__(
        self,
        server_url: str = DEFAULT_SERVER_URL,
        *,
        enabled: bool | None = None,
        idle_expiry_seconds: float | None = None,
        max_turns: int | None = None,
        request_timeout: float = 5,
    ) -> None:
        self.server_url = (server_url or DEFAULT_SERVER_URL).rstrip("/")
        self.enabled = _env_bool("DAEMON_REUSE_OPENCODE_SESSIONS") if enabled is None else enabled
        self.idle_expiry_seconds = float(
            idle_expiry_seconds if idle_expiry_seconds is not None
            else os.environ.get("DAEMON_OPENCODE_SESSION_IDLE_SECONDS", 900)
        )
        self.max_turns = max(
            1,
            int(max_turns if max_turns is not None
                else os.environ.get("DAEMON_OPENCODE_SESSION_MAX_TURNS", 20)),
        )
        self.request_timeout = request_timeout
        self._session_id: str | None = None
        self._turns = 0
        self._last_used = 0.0
        self._lock = threading.RLock()

    @property
    def session_id(self) -> str | None:
        with self._lock:
            return self._session_id

    @property
    def turns(self) -> int:
        with self._lock:
            return self._turns

    def acquire(self) -> str | None:
        """Return a reusable session, creating/resetting it as needed."""
        if not self.enabled:
            return None
        with self._lock:
            if self._session_id and not self._healthy_locked():
                self._close_locked()
            if self._session_id and (
                self._expired() or self._turns >= self.max_turns
            ):
                self._close_locked()
            if not self._session_id:
                self._session_id = self._create()
                self._turns = 0
            if self._session_id:
                self._turns += 1
                self._last_used = time.monotonic()
            return self._session_id

    def health_check(self) -> bool:
        """Validate current session and discard it when OpenCode lost it."""
        if not self.enabled:
            return True
        with self._lock:
            if not self._session_id:
                return True
            if self._healthy_locked():
                return True
            self._close_locked()
            return False

    def record_result(self, success: bool) -> None:
        """Refresh activity on success; discard a broken conversation."""
        if not self.enabled:
            return
        with self._lock:
            if success:
                self._last_used = time.monotonic()
            else:
                self._close_locked()

    def reset(self) -> None:
        with self._lock:
            self._close_locked()

    def close(self) -> None:
        """Best-effort shutdown cleanup."""
        with self._lock:
            self._close_locked()

    def _expired(self) -> bool:
        return bool(self._last_used and time.monotonic() - self._last_used >= self.idle_expiry_seconds)

    def _create(self) -> str | None:
        try:
            response = requests.post(f"{self.server_url}/session", json={}, timeout=self.request_timeout)
            if response.status_code >= 400:
                return None
            data = response.json()
            return data.get("id") or data.get("session_id")
        except Exception as exc:
            logger.warning("Reusable OpenCode session creation failed (%s)", type(exc).__name__)
            return None

    def _healthy_locked(self) -> bool:
        try:
            response = requests.get(
                f"{self.server_url}/session/{self._session_id}",
                timeout=self.request_timeout,
            )
            return response.status_code < 400
        except Exception:
            return False

    def _close_locked(self) -> None:
        session_id = self._session_id
        self._session_id = None
        self._turns = 0
        self._last_used = 0.0
        if not session_id:
            return
        try:
            requests.delete(f"{self.server_url}/session/{session_id}", timeout=self.request_timeout)
        except Exception as exc:
            logger.debug("Reusable OpenCode session cleanup failed (%s)", type(exc).__name__)


# Match existing Opencode* naming while keeping the protocol's OpenCode spelling.
OpencodeSessionManager = OpenCodeSessionManager
