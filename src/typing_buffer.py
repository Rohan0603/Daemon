# src/typing_buffer.py
from __future__ import annotations
import logging
from collections import deque
from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)

try:
    from pynput import keyboard
except Exception:
    logger.warning("pynput not available — TypingBuffer disabled")
    keyboard = None  # type: ignore


class TypingBuffer(QObject):
    text_updated = pyqtSignal()

    def __init__(self, max_chars: int = 500, parent=None):
        super().__init__(parent)
        self._buffer = deque(maxlen=max_chars)
        self._listener = None

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
            self.text_updated.emit()
        elif key == keyboard.Key.backspace:
            if self._buffer:
                self._buffer.pop()
                self.text_updated.emit()
        elif key == keyboard.Key.enter:
            self._buffer.append('\n')
            self.text_updated.emit()
        elif key == keyboard.Key.tab:
            self._buffer.append('\t')
            self.text_updated.emit()
        elif key == keyboard.Key.space:
            self._buffer.append(' ')
            self.text_updated.emit()
