# src/thought_log_dialog.py
import logging
from pathlib import Path
from PyQt6.QtCore import QTimer
from src.constants import THOUGHTS_LOG_PATH
from .data_viewer_dialog import DataViewerDialog

logger = logging.getLogger(__name__)


class ThoughtLogDialog(DataViewerDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(title="Daemon: Brain Scan (Internal Monologue)", content="", parent=parent)

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
