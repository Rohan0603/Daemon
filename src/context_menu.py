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
    restart_brain = pyqtSignal()
    thought_log   = pyqtSignal()
    settings_requested = pyqtSignal()
    sleep_toggle = pyqtSignal(bool)
    mute_toggle = pyqtSignal(bool)
    wipe_memory = pyqtSignal()


class PetContextMenu(QMenu):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.signals = _Signals()

        logger.debug("Context menu created")

        self._pin_action = self.addAction("📌 Pin to Screen", lambda: self.signals.pin_toggle.emit())
        self._pin_action.setCheckable(True)
        
        self._sleep_action = self.addAction("💤 Force Sleep", lambda checked: self.signals.sleep_toggle.emit(checked))
        self._sleep_action.setCheckable(True)
        
        self._mute_action = self.addAction("🔇 Mute Voice", lambda checked: self.signals.mute_toggle.emit(checked))
        self._mute_action.setCheckable(True)
        
        self.addAction("⚙️ Settings...", self.signals.settings_requested.emit)
        
        self.addSeparator()
        
        brain_ops = self.addMenu("🧠 Brain Ops ▸")
        brain_ops.addAction("What do I remember?", self.signals.recall_memory.emit)
        brain_ops.addAction("Show recent history", self.signals.recall_history.emit)
        brain_ops.addAction("View Brain Scan", self.signals.thought_log.emit)
        brain_ops.addSeparator()
        brain_ops.addAction("⚡ Defibrillate (Restart)", self.signals.restart_brain.emit)
        brain_ops.addAction("⚠️ Lobotomy (Wipe All Data)", self.signals.wipe_memory.emit)
        
        self.addSeparator()
        
        self.addAction("💀 Kill Daemon", self.signals.quit_requested.emit)

    def set_pinned(self, pinned: bool) -> None:
        self._pin_action.setChecked(pinned)
        
    def set_sleep(self, sleeping: bool) -> None:
        self._sleep_action.setChecked(sleeping)
        
    def set_muted(self, muted: bool) -> None:
        self._mute_action.setChecked(muted)
