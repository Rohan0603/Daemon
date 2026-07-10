# src/llm/ollama_manager.py
from __future__ import annotations
import logging, shutil, threading
from typing import Any
from PyQt6.QtCore import QObject, QProcess, QTimer, pyqtSignal
import requests
from pathlib import Path

logger = logging.getLogger(__name__)

OLLAMA_HEALTH_URL = "http://127.0.0.1:11434/api/tags"
OLLAMA_MAX_RETRIES = 10
OLLAMA_RETRY_INTERVAL_MS = 2000
OLLAMA_KILL_WAIT_MS = 5000


class OllamaManager(QObject):
    status_changed = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    ready = pyqtSignal()

    def __init__(self, modelfile_path: str | Path = "data/Modelfile",
                 model_name: str = "llama3.2-1b-q8:latest",
                 ollama_url: str = "http://127.0.0.1:11434",
                 parent: Any = None):
        super().__init__(parent)
        self._modelfile_path = Path(modelfile_path) if not isinstance(modelfile_path, Path) else modelfile_path
        self._model_name = model_name
        self._ollama_url = ollama_url.strip("/")
        self._process: QProcess | None = None
        self._health_timer: QTimer | None = None
        self._retries = 0
        self._warming = False

    def start(self) -> None:
        self.status_changed.emit("starting")
        if self._is_ollama_running():
            logger.info("Ollama already running on %s", self._ollama_url)
            self._ensure_model()
            self.status_changed.emit("ready")
            self.ready.emit()
            self._warm_model_async()
            return
        ollama_path = self._find_ollama()
        if not ollama_path:
            self.error_occurred.emit("ollama_not_found")
            self.status_changed.emit("error")
            return
        self._ensure_model()
        self._spawn_serve(ollama_path)

    def stop(self) -> None:
        self._stop_health_timer()
        if self._process and self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.terminate()
            if not self._process.waitForFinished(OLLAMA_KILL_WAIT_MS):
                self._process.kill()
                self._process.waitForFinished(2000)
        self._process = None
        self.status_changed.emit("stopped")

    def _find_ollama(self) -> str | None:
        path = shutil.which("ollama")
        if path:
            return path
        extra = ["C:\\Program Files\\Ollama\\ollama.exe",
                 "C:\\Program Files (x86)\\Ollama\\ollama.exe"]
        for p in extra:
            if Path(p).exists():
                return p
        return None

    def _is_ollama_running(self) -> bool:
        try:
            resp = requests.get(OLLAMA_HEALTH_URL, timeout=3)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def _ensure_model(self) -> None:
        # We no longer automatically create daemon-local or run custom modelfiles
        pass

    def _warm_model(self) -> None:
        try:
            payload = {
                "model": self._model_name,
                "messages": [{"role": "user", "content": "ping"}],
                "stream": False,
                "keep_alive": "10m",
                "options": {"num_predict": 1},
            }
            resp = requests.post(
                f"{self._ollama_url}/api/chat",
                json=payload,
                timeout=120,
            )
            if resp.status_code == 200:
                logger.info("Model %s warmed up in memory", self._model_name)
        except requests.RequestException as exc:
            logger.debug("Model warm-up skipped (non-critical): %s", exc)

    def _warm_model_async(self) -> None:
        """Warm the model off the caller's thread so the UI never blocks."""
        if self._warming:
            return
        self._warming = True
        def _run() -> None:
            try:
                self._warm_model()
            finally:
                self._warming = False
        threading.Thread(target=_run, daemon=True).start()

    def _spawn_serve(self, ollama_path: str) -> None:
        self._process = QProcess(self)
        self._process.setProgram(ollama_path)
        self._process.setArguments(["serve"])
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.ForwardedChannels)
        self._process.started.connect(lambda: logger.info("ollama serve started"))
        self._process.finished.connect(self._on_process_finished)
        self._process.start()
        self._start_health_check()

    def _start_health_check(self) -> None:
        self._retries = 0
        self._health_timer = QTimer(self)
        self._health_timer.timeout.connect(self._check_health)
        self._health_timer.start(OLLAMA_RETRY_INTERVAL_MS)

    def _stop_health_timer(self) -> None:
        if self._health_timer:
            self._health_timer.stop()
            self._health_timer = None

    def _check_health(self) -> None:
        if self._is_ollama_running():
            self._stop_health_timer()
            self.status_changed.emit("ready")
            self.ready.emit()
            self._warm_model_async()
            return
        self._retries += 1
        if self._retries >= OLLAMA_MAX_RETRIES:
            self._stop_health_timer()
            self.error_occurred.emit("ollama_serve_timeout")
            self.status_changed.emit("error")

    def _on_process_finished(self, exit_code: int, exit_status) -> None:
        logger.warning("ollama serve exited with code %d", exit_code)
        self.status_changed.emit("stopped")
        if exit_code != 0:
            self._retry_or_error()

    def _retry_or_error(self) -> None:
        if self._retries < 3:
            self._retries += 1
            QTimer.singleShot(5000, self.start)
        else:
            self.error_occurred.emit("ollama_crashed")
            self.status_changed.emit("error")

    def _run_ollama_command(self, args: list[str]) -> None:
        ollama_path = self._find_ollama()
        if not ollama_path:
            return
        proc = QProcess(self)
        proc.setProgram(ollama_path)
        proc.setArguments(args)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.ForwardedChannels)
        proc.start()
        proc.waitForFinished(60000)
