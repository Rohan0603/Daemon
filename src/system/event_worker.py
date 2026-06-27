import json
import time
import requests
import logging
from PyQt6.QtCore import QThread, pyqtSignal

from src.config import DEFAULT_SERVER_URL

logger = logging.getLogger(__name__)


class EventStreamWorker(QThread):
    MAX_CONSECUTIVE_FAILURES = 10

    lsp_error_detected = pyqtSignal(dict)
    lsp_error_cleared = pyqtSignal()
    command_completed = pyqtSignal(str, int)
    file_edited = pyqtSignal(str)
    auth_failed = pyqtSignal()

    def __init__(self, server_url: str = DEFAULT_SERVER_URL):
        super().__init__()
        self.server_url = server_url
        self._running = True
        self._response = None
        self._consecutive_failures = 0

    def run(self):
        backoff = 3
        while self._running:
            try:
                self._response = requests.get(f"{self.server_url}/event", stream=True, timeout=60)
                if self._response.status_code in (401, 403):
                    logger.error(
                        "EventStreamWorker auth failure (HTTP %d)",
                        self._response.status_code,
                    )
                    self.auth_failed.emit()
                    self._running = False
                    break
                self._response.raise_for_status()
                backoff = 3
                self._consecutive_failures = 0
                for line in self._response.iter_lines():
                    if not self._running:
                        break
                    if line:
                        decoded = line.decode('utf-8')
                        if decoded.startswith('data: '):
                            try:
                                event_data = json.loads(decoded[6:])
                                self._handle_event(event_data)
                            except json.JSONDecodeError as e:
                                logger.warning("Failed to parse SSE JSON: %s", e)
            except Exception as e:
                if self._running:
                    self._consecutive_failures += 1
                    if self._consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
                        logger.info("EventStreamWorker disabled")
                        self._running = False
                        break
                    logger.error("EventStreamWorker network error: %s", e)
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 15)
            finally:
                if self._response is not None:
                    try:
                        self._response.close()
                    except Exception:
                        pass
                    self._response = None

    def _handle_event(self, data: dict):
        if "EventLspUpdated" in data:
            payload = data["EventLspUpdated"]
            has_error = any(d.get("severity") == "ERROR" for d in payload.get("diagnostics", []))
            if has_error:
                self.lsp_error_detected.emit(payload)
            else:
                self.lsp_error_cleared.emit()
        elif "EventCommandExecuted" in data:
            payload = data["EventCommandExecuted"]
            exit_code = payload.get("exit_code")
            if exit_code is None:
                exit_code = 0
            self.command_completed.emit(payload.get("command", ""), exit_code)
        elif "EventFileEdited" in data:
            self.file_edited.emit(data["EventFileEdited"].get("filepath", ""))

    def stop(self):
        self._running = False
        if self._response:
            try:
                self._response.close()
            except Exception:
                pass
        self.wait()