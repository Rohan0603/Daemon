# src/typing_buffer.py
from __future__ import annotations
import logging
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

    def __init__(self, max_chars: int = 500, parent=None):
        super().__init__(parent)
        self._buffer = deque(maxlen=max_chars)
        self._listener = None
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(50)  # 50ms debounce
        self._debounce_timer.timeout.connect(self.text_updated.emit)
        self.debounce_restart.connect(self._debounce_timer.start)

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

    def char_count(self) -> int:
        return len(self._buffer)

    def get_context(self, max_chars: int = 300) -> str:
        if not self._buffer:
            return ""
        text = "".join(self._buffer)
        text = text[-max_chars:]
        formatted = text.replace("\n", "\n  > ")
        return f"Recent Typing:\n  > {formatted}"

    def _on_press(self, key):
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
