# src/thought_log_dialog.py
import logging
from pathlib import Path
from PyQt6.QtWidgets import QDialog, QTextEdit, QVBoxLayout
from PyQt6.QtCore import QTimer
from src.constants import THOUGHTS_LOG_PATH

logger = logging.getLogger(__name__)


class ThoughtLogDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Daemon: Brain Scan (Internal Monologue)")
        self.setFixedSize(600, 400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._text_edit = QTextEdit(self)
        self._text_edit.setReadOnly(True)
        self._text_edit.setStyleSheet(
            "QTextEdit {"
            "  background-color: #0d0d0d;"
            "  color: #00ff00;"
            "  font-family: Consolas, monospace;"
            "  font-size: 12px;"
            "  border: none;"
            "}"
        )
        layout.addWidget(self._text_edit)

        self._last_content = ""
        self._update_timer = QTimer(self)
        self._update_timer.setInterval(1000)
        self._update_timer.timeout.connect(self._update_log)
        self._update_timer.start()
        self._update_log()

    def _update_log(self) -> None:
        try:
            content = Path(THOUGHTS_LOG_PATH).read_text(encoding="utf-8")
        except (FileNotFoundError, OSError):
            content = "No thoughts recorded yet..."
        if content == self._last_content:
            return
        self._last_content = content
        self._text_edit.setPlainText(content)
        scrollbar = self._text_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
