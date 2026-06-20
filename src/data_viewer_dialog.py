# src/data_viewer_dialog.py
from PyQt6.QtWidgets import QDialog, QTextEdit, QVBoxLayout
from typing import Callable, Union

class DataViewerDialog(QDialog):
    def __init__(self, title: str, content: Union[str, Callable[[], str]], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
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

        if callable(content):
            text = content()
        else:
            text = content
            
        self._text_edit.setPlainText(text)
        scrollbar = self._text_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
