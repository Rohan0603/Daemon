# src/context_menu.py
import logging
from PyQt6.QtWidgets import QMenu, QApplication
from PyQt6.QtCore import pyqtSignal, QObject

logger = logging.getLogger(__name__)


class _Signals(QObject):
    quit_requested = pyqtSignal()
    recall_memory = pyqtSignal()
    recall_history = pyqtSignal()
    pin_toggle    = pyqtSignal()


class PetContextMenu(QMenu):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.signals = _Signals()

        logger.debug("Context menu created")

        self.addAction("What do you remember?", self.signals.recall_memory.emit)
        self.addAction("Show recent history", self.signals.recall_history.emit)
        self._pin_action = self.addAction("Pin position", self.signals.pin_toggle.emit)
        self._pin_action.setCheckable(True)
        self.addSeparator()
        self.addAction("Quit Daemon", self.signals.quit_requested.emit)

    def set_pinned(self, pinned: bool) -> None:
        self._pin_action.setChecked(pinned)

