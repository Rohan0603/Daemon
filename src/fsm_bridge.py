from PyQt6.QtCore import QObject, pyqtSignal


class FSMActionBridge(QObject):
    """Thread-safe bridge between MCP server thread and PyQt main thread.

    Emits a pyqtSignal from any thread. PyQt6 automatically uses
    QueuedConnection when the signal is connected to a slot on the main
    thread, so no mutex is needed.
    """

    request = pyqtSignal(str, object, object)  # action, target_x, target_y
    toast_request = pyqtSignal(str, str)  # title, message
    summarize_requested = pyqtSignal(str, str) # providerID, modelID
    reminder_request = pyqtSignal(str, object) # action, data

    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_action = None

    def emit_request(self, action: str, target_x=None, target_y=None):
        self._last_action = action
        self.request.emit(action, target_x, target_y)

    def emit_toast(self, title: str, message: str):
        self.toast_request.emit(title, message)

    def emit_summarize_requested(self, provider_id: str, model_id: str) -> None:
        self.summarize_requested.emit(provider_id, model_id)
