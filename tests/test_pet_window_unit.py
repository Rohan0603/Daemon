import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QSystemTrayIcon
from src.pet_window import PetWindow


@pytest.mark.fast
def test_onboarding_bubbles_skipped_if_done(app):
    with patch("src.ui.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.ui.pet_window.APMWorker"):
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
    with patch("src.ui.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.ui.pet_window.APMWorker"), \
         patch("src.ui.pet_window.MemoryManager", return_value=mock_firebase):
        mem_path = str(tmp_path / "test_memory.json")
        hist_path = str(tmp_path / "test_history.json")
        window = PetWindow(opencode_enabled=False, memory_path=mem_path, history_path=hist_path)
        window._memory.remember("name", "TestUser")
        window._memory.remember("lang", "Python")
        with patch("src.ui.data_viewer_dialog.DataViewerDialog") as mock_dialog:
            mock_instance = MagicMock()
            mock_dialog.return_value = mock_instance
            window._on_recall_memory()
            mock_dialog.assert_called_once()
            content_callable = mock_dialog.call_args[0][1]
            content = content_callable()
            assert "TestUser" in content
            assert "Python" in content
            mock_instance.exec.assert_called_once()


@pytest.mark.fast
def test_bubble_queue_discards_stale_items(app, monkeypatch):
    from src.constants import BUBBLE_QUEUE_TTL_SECS
    import time as _real_time
    with patch("src.ui.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.ui.pet_window.APMWorker"), \
         patch("src.ui.pet_window.MCPServer"):
        window = PetWindow(opencode_enabled=False, initial_state={"first_run_done": True})
        BASE = 1000.0
        monkeypatch.setattr("time.time", lambda: BASE)
        window._bubble_timer_ms = 5000
        window._show_bubble("stale message")
        assert len(window._bubble_queue) == 1

        monkeypatch.setattr("time.time", lambda: BASE + BUBBLE_QUEUE_TTL_SECS + 1)
        window._bubble_text = ""
        window._bubble_timer_ms = 0
        now = BASE + BUBBLE_QUEUE_TTL_SECS + 1
        fresh = [(t, ts) for t, ts in window._bubble_queue if now - ts <= BUBBLE_QUEUE_TTL_SECS]
        assert len(fresh) == 0


@pytest.mark.fast
def test_bubble_queue_cleared_on_sleep_entry(app):
    from src.pet_fsm import PetState
    with patch("src.ui.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.ui.pet_window.APMWorker"), \
         patch("src.ui.pet_window.MCPServer"), \
         patch("src.ui.pet_window.BehaviorController"):
        window = PetWindow(opencode_enabled=False)
        window._bubble_queue = [("msg1", 100.0), ("msg2", 200.0)]
        window._bubble_timer_ms = 5000
        window._fsm.current_state = PetState.IDLE
        window._fsm.update = lambda dt, ctx: PetState.SLEEP
        window._tick()
        assert len(window._bubble_queue) == 0
        assert window._bubble_text == ""


@pytest.mark.fast
def test_boredom_timer_reset_on_sleep_entry(app):
    from src.pet_fsm import PetState
    from src.constants import BOREDOM_TIMEOUT_SEC
    with patch("src.ui.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.ui.pet_window.APMWorker"), \
         patch("src.ui.pet_window.MCPServer"), \
         patch("src.ui.pet_window.BehaviorController"):
        window = PetWindow(opencode_enabled=False)
        window._boredom_timer_ms = 90000
        window._fsm.current_state = PetState.IDLE
        window._fsm.update = lambda dt, ctx: PetState.SLEEP
        window._tick()
        assert window._boredom_timer_ms == BOREDOM_TIMEOUT_SEC * 1000
