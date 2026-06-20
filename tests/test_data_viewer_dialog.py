import pytest
from PyQt6.QtWidgets import QApplication
from src.data_viewer_dialog import DataViewerDialog

def test_data_viewer_dialog_initialization(qapp):
    dialog = DataViewerDialog(title="Test Viewer", content="Sample content\nLine 2")
    assert dialog.windowTitle() == "Test Viewer"
    assert "Sample content" in dialog._text_edit.toPlainText()
