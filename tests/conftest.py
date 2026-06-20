"""Shared fixtures for all Daemon tests."""

from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtWidgets import QApplication


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

@pytest.fixture
def mock_background_workers():
    """Comprehensive mocking of PetWindow background workers.

    Use this fixture in any test that instantiates PetWindow to avoid
    real worker threads, network calls, and file I/O during tests.
    """
    with patch("src.pet_window.TTSWorker"), \
         patch("src.pet_window.MCPServer"), \
         patch("src.pet_window.TypingBuffer") as mock_tb, \
         patch("src.pet_window.APMWorker"), \
         patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.OpencodeWorker"), \
         patch("src.pet_window.MemoryManager") as mock_mem, \
         patch("src.pet_window.History") as mock_hist, \
         patch("src.pet_window.DiaryStore") as mock_diary:
        # Configure mocks
        mock_tb.return_value.get_context.return_value = ""
        mock_mem.return_value = _mock_firebase_diary(mock_mem.return_value)
        mock_hist.read_local.return_value = None
        mock_hist.write_local.return_value = None
        mock_diary.read.return_value = None
        mock_diary.write.return_value = None
        yield


def _mock_firebase_diary(m: MagicMock) -> MagicMock:
    """Set sensible defaults for diary methods on a mock MemoryManager."""
    m.read_local_diary.return_value = None       # no local file -> fetch from Firebase
    m.fetch_all_diary_entries.return_value = []   # Firebase has no entries
    m.write_local_diary = MagicMock()
    m.push_pending_diaries.return_value = 0
    return m
