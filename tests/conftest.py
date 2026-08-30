"""Shared fixtures for all Daemon tests."""

from unittest.mock import MagicMock, patch
import os

import pytest
from PyQt6.QtWidgets import QApplication

# Keep module imports independent from developer machine credentials. Production
# startup still validates that a real runtime credential is configured.
os.environ.setdefault("OPENCODE_API_KEY", "test-opencode-key")


# ── Qt Application Fixtures ─────────────────────────────────────────────

@pytest.fixture(scope="session")
def qapp():
    """Session-scoped QApplication instance. All Qt-dependent tests use this."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def app(qapp):
    """Alias for qapp — use this in test function signatures for clarity."""
    return qapp


# ── PetWindow Background Worker Mocking ────────────────────────────────

from unittest.mock import MagicMock

@pytest.fixture
def mock_background_workers():
    with patch("src.ui.pet_window.TTSWorker"), \
         patch("src.ui.pet_window.MCPServer"), \
         patch("src.ui.pet_window.TypingBuffer") as mock_tb, \
         patch("src.ui.pet_window.APMWorker"), \
         patch("src.ui.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.ui.pet_window.OpencodeWorker"), \
         patch("src.ui.pet_window.MemoryManager") as mock_mem, \
         patch("src.ui.pet_window.History") as mock_hist, \
         patch("src.ui.pet_window.DiaryStore") as mock_diary:
        mock_tb.return_value.get_context.return_value = ""
        mock_mem.return_value = _mock_firebase_diary(mock_mem.return_value)
        mock_hist.read_local.return_value = None
        mock_hist.write_local.return_value = None
        mock_diary.read.return_value = None
        mock_diary.write.return_value = None
        yield

def _mock_firebase_diary(m: MagicMock) -> MagicMock:
    m.read_local_diary.return_value = None       
    m.fetch_all_diary_entries.return_value = []   
    m.write_local_diary = MagicMock()
    m.push_pending_diaries.return_value = 0
    return m

from src.brain_store import BrainStore

@pytest.fixture(autouse=True)
def clear_brain_store_instances(monkeypatch):
    BrainStore._instances.clear()
    monkeypatch.setattr(BrainStore, '_migrate_v1_data', lambda self: None)

@pytest.fixture
def safe_pet_window(app):
    with patch("src.ui.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.ui.pet_window.APMWorker"), \
         patch("src.ui.pet_window.MCPServer"), \
         patch("src.ui.pet_window.BehaviorController"), \
         patch("src.llm.ollama_manager.OllamaManager"), \
         patch("src.ui.pet_window.EventStreamWorker"), \
         patch("src.ui.pet_window.TTSWorker"):
        
        from src.ui.pet_window import PetWindow
        window = PetWindow(opencode_enabled=False, initial_state={"first_run_done": True})
        
        yield window
        
        # Fast teardown without 15s ghost summarization
        window._force_quit = True
        if hasattr(window, '_fsm_timer'): window._fsm_timer.stop()
        if hasattr(window, '_behavior_timer'): window._behavior_timer.stop()
        if hasattr(window, '_boot_timer'): window._boot_timer.stop()
        if hasattr(window, '_health_timer'): window._health_timer.stop()
        if hasattr(window, '_firestore_sync_timer'): window._firestore_sync_timer.stop()
        
        window.close()
        window.deleteLater()
