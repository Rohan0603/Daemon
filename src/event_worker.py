import json
import time
import requests
from PyQt6.QtCore import QThread, pyqtSignal

class EventStreamWorker(QThread):
    lsp_error_detected = pyqtSignal(dict)
    lsp_error_cleared = pyqtSignal()
    command_completed = pyqtSignal(str, int)
    file_edited = pyqtSignal(str)

    def __init__(self, server_url: str = "http://127.0.0.1:4096"):
        super().__init__()
        self.server_url = server_url
        self._running = True

    def run(self):
        backoff = 3
        while self._running:
            try:
                with requests.get(f"{self.server_url}/event", stream=True, timeout=5) as r:
                    r.raise_for_status()
                    backoff = 3
                    for line in r.iter_lines():
                        if not self._running:
                            break
                        if line:
                            decoded = line.decode('utf-8')
                            if decoded.startswith('data: '):
                                try:
                                    event_data = json.loads(decoded[6:])
                                    self._handle_event(event_data)
                                except json.JSONDecodeError:
                                    pass
            except Exception:
                if self._running:
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 15)

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
            self.command_completed.emit(payload.get("command", ""), payload.get("exit_code", 0))
        elif "EventFileEdited" in data:
            self.file_edited.emit(data["EventFileEdited"].get("filepath", ""))

    def stop(self):
        self._running = False
        self.wait()
