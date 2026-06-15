# src/apm_worker.py
from __future__ import annotations
import logging
import time
from collections import deque
from PyQt6.QtCore import QThread, pyqtSignal
from src.constants import APM_WINDOW_SECONDS

logger = logging.getLogger(__name__)

try:
    from pynput import keyboard as _kb
except Exception:
    _kb = None


class APMWorker(QThread):
    apm_updated    = pyqtSignal(int)
    listener_failed = pyqtSignal(str)
    hotkey_triggered = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._events: deque = deque(maxlen=APM_WINDOW_SECONDS * 10)
        self._running = False
        self.apm: int = 0

    def run(self) -> None:
        try:
            from pynput import keyboard, mouse
        except Exception as e:
            self.listener_failed.emit(f"pynput import failed: {e}")
            return

        logger.debug("Starting pynput listeners")

        def record(_):
            self._events.append(time.monotonic())

        try:
            kb_listener = keyboard.Listener(on_press=record)
            ms_listener = mouse.Listener(on_click=lambda *_: record(None))
            kb_listener.start()
            ms_listener.start()
        except Exception as e:
            logger.warning("pynput listener failed: %s", e)
            self.listener_failed.emit(f"pynput listener failed: {e}")
            return

        if _kb is not None:
            try:
                self._hotkeys = _kb.GlobalHotKeys({"<ctrl>+<alt>+d": self._on_hotkey})
                self._hotkeys.start()
            except Exception:
                self._hotkeys = None
        else:
            self._hotkeys = None

        self._running = True
        last_emit = time.monotonic()

        while self._running:
            now = time.monotonic()
            cutoff = now - APM_WINDOW_SECONDS
            while self._events and self._events[0] < cutoff:
                self._events.popleft()

            if now - last_emit >= 2.0:
                self.apm = int(len(self._events) / (APM_WINDOW_SECONDS / 60))
                self.apm_updated.emit(self.apm)
                last_emit = now

            self.msleep(200)

        kb_listener.stop()
        ms_listener.stop()
        if self._hotkeys is not None:
            try:
                self._hotkeys.stop()
            except Exception:
                pass

    def _on_hotkey(self) -> None:
        self.hotkey_triggered.emit()

    def stop(self) -> None:
        self._running = False
        if hasattr(self, "_hotkeys") and self._hotkeys is not None:
            try:
                self._hotkeys.stop()
            except Exception:
                pass
        self.wait(3000)
