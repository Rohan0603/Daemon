import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QSystemTrayIcon
from src.pet_window import PetWindow


@pytest.mark.fast
def test_onboarding_bubbles_skipped_if_done(app):
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"):
        window = PetWindow(
            opencode_enabled=True,
            skill_ready=True,
            initial_state={"first_run_done": True},
        )
        assert len(window._bubble_queue) == 0


@pytest.mark.fast
def test_recall_memory_opens_dialog(app, tmp_path):
    mock_firebase = MagicMock()
    mock_firebase.load_current_brain.return_value = {}
    mock_firebase.read_local_diary.return_value = None
    mock_firebase.fetch_all_diary_entries.return_value = []
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"), \
         patch("src.pet_window.MemoryManager", return_value=mock_firebase):
        mem_path = str(tmp_path / "test_memory.json")
        hist_path = str(tmp_path / "test_history.json")
        window = PetWindow(opencode_enabled=False, memory_path=mem_path, history_path=hist_path)
        window._memory.remember("name", "TestUser")
        window._memory.remember("lang", "Python")
        with patch("src.data_viewer_dialog.DataViewerDialog") as mock_dialog:
            mock_instance = MagicMock()
            mock_dialog.return_value = mock_instance
            window._on_recall_memory()
            mock_dialog.assert_called_once()
            content_callable = mock_dialog.call_args[0][1]
            content = content_callable()
            assert "TestUser" in content
            assert "Python" in content
            mock_instance.exec.assert_called_once()
