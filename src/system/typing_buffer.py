# src/system/typing_buffer.py
from __future__ import annotations
import ctypes
import logging
import time
from collections import deque
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

logger = logging.getLogger(__name__)

try:
    from pynput import keyboard
except Exception:
    logger.warning("pynput not available — TypingBuffer disabled")
    keyboard = None  # type: ignore

class TypingBuffer(QObject):
    text_updated = pyqtSignal()
    debounce_restart = pyqtSignal()  # emitted from pynput thread; main thread restarts timer

    def __init__(self, max_chars: int = 500, parent=None, idle_timeout: int = 60):
        super().__init__(parent)
        self._buffer = deque(maxlen=max_chars)
        self._last_keystroke_time = ctypes.c_double(time.time())
        self._idle_timeout = idle_timeout
        self._listener = None
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(50)  # 50ms debounce
        self._debounce_timer.timeout.connect(self.text_updated.emit)
        self.debounce_restart.connect(self._debounce_timer.start)
        self._idle_check_timer = QTimer()
        self._idle_check_timer.setInterval(30000)
        self._idle_check_timer.timeout.connect(self._check_idle)
        self._idle_check_timer.start()

    def start(self):
        if keyboard is None:
            logger.warning("pynput unavailable, cannot start TypingBuffer")
            return
        try:
            self._listener = keyboard.Listener(on_press=self._on_press)
            self._listener.start()
        except Exception:
            logger.exception("Failed to start TypingBuffer listener")
            self._listener = None

    def stop(self):
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None
        self._debounce_timer.stop()
        self._idle_check_timer.stop()

    def _check_idle(self):
        if time.time() - self._last_keystroke_time.value > self._idle_timeout:
            if self._buffer:
                logger.debug("TypingBuffer proactive idle clear: removing %d chars", len(self._buffer))
                self._buffer.clear()

    def char_count(self) -> int:
        return len(self._buffer)

    def get_context(self, max_chars: int = 300) -> str:
        # Clear buffer if idle too long (stale typing from earlier session)
        if time.time() - self._last_keystroke_time.value > self._idle_timeout:
            if self._buffer:
                logger.debug("TypingBuffer idle timeout: clearing %d chars", len(self._buffer))
                self._buffer.clear()
            return ""
        if not self._buffer:
            return ""
        text = "".join(self._buffer)
        text = text[-max_chars:]
        formatted = text.replace("\n", "\n  > ")
        return f"Recent Typing:\n  > {formatted}"

    def _on_press(self, key):
        self._last_keystroke_time.value = time.time()
        if hasattr(key, 'char') and key.char is not None:
            self._buffer.append(key.char)
        elif key == keyboard.Key.backspace:
            if self._buffer:
                self._buffer.pop()
            else:
                return  # Nothing to pop, don't restart timer
        elif key == keyboard.Key.enter:
            self._buffer.append('\n')
        elif key == keyboard.Key.tab:
            self._buffer.append('\t')
        elif key == keyboard.Key.space:
            self._buffer.append(' ')
        else:
            return  # Non-character key, don't restart timer
        # Debounce timer emits text_updated after 50ms of inactivity.
        # Restart on every keystroke to coalesce bursts.
        self.debounce_restart.emit()