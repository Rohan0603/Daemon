import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import random
from PyQt6.QtCore import QTimer
from src.pet_window import PetWindow
from src.pet_fsm import PetState

# pytest markers

@pytest.mark.fast
def test_onboarding_bubbles(app):
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"):
        window = PetWindow(opencode_enabled=True, skill_ready=True, initial_state={"first_run_done": False})
        
        assert len(window._bubble_queue) == 3
        assert window._bubble_queue[0] == "Hey! I'm Kenny! Nice to meet ya."
        assert window._bubble_queue[1] == "Double-click me if you wanna ask opencode anything, alright?"
        assert window._bubble_queue[2] == "Right-click me for options. D-d-don't click too hard though!"

@pytest.mark.fast
def test_bubble_queue_shows_immediately_when_idle(app):
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"):
        window = PetWindow(opencode_enabled=False, initial_state={"first_run_done": True})
        window._bubble_queue.clear()
        window._show_bubble("hello")
        assert window._bubble_text == "hello"
        assert window._bubble_timer_ms > 0

@pytest.mark.fast
def test_bubble_queue_appends_when_active(app):
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"):
        window = PetWindow(opencode_enabled=False, initial_state={"first_run_done": True})
        window._bubble_queue.clear()
        window._show_bubble("first")
        assert window._bubble_text == "first"
        window._show_bubble("second")
        assert window._bubble_text == "first"  # still showing
        assert window._bubble_queue == ["second"]

@pytest.mark.fast
def test_bubble_queue_drops_when_full(app):
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"):
        window = PetWindow(opencode_enabled=False, initial_state={"first_run_done": True})
        window._bubble_queue.clear()
        # BUBBLE_QUEUE_MAX_SIZE = 10, first displays immediately, rest queue
        for i in range(11):  # 1 displayed + 10 queued = 11 total before drop
            window._show_bubble(f"bubble{i}")
        # First was displayed immediately, 10 queued
        # 11th should be dropped
        assert len(window._bubble_queue) == 10
        window._show_bubble("overflow")  # should be dropped
        assert len(window._bubble_queue) == 10

@pytest.mark.fast
def test_bubble_queue_immediate_replaces_current(app):
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"):
        window = PetWindow(opencode_enabled=False, initial_state={"first_run_done": True})
        window._bubble_queue = ["queued"]
        window._show_bubble("first")
        assert window._bubble_text == "first"
        # Queue stays intact for after this bubble
        assert window._bubble_queue == ["queued"]

@pytest.mark.fast
def test_bubble_tick_dequeues_next(app):
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"):
        window = PetWindow(opencode_enabled=False, initial_state={"first_run_done": True})
        window._bubble_queue.clear()
        window._show_bubble("first")
        window._show_bubble("second")
        assert window._bubble_queue == ["second"]
        # Simulate bubble expiry
        window._bubble_timer_ms = 1
        window._tick()
        assert window._bubble_text == "second"
        assert window._bubble_queue == []

@pytest.mark.fast
def test_bubble_short_text_gets_shorter_duration(app):
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"):
        window = PetWindow(opencode_enabled=False, initial_state={"first_run_done": True})
        window._bubble_queue.clear()
        window._show_bubble("hi")
        assert window._bubble_timer_ms == 4000

@pytest.mark.fast
def test_bubble_long_text_gets_full_duration(app):
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"):
        window = PetWindow(opencode_enabled=False, initial_state={"first_run_done": True})
        window._bubble_queue.clear()
        window._show_bubble("x" * 41)
        assert window._bubble_timer_ms == 8000

@pytest.mark.fast
def test_clear_bubble_queue_clears_current_and_pending(app):
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"):
        window = PetWindow(opencode_enabled=False, initial_state={"first_run_done": True})
        window._bubble_queue.clear()
        window._show_bubble("first")
        window._show_bubble("second")
        window._show_bubble("third")
        assert window._bubble_text == "first"
        assert len(window._bubble_queue) == 2
        window._clear_bubble_queue()
        assert window._bubble_text == ""
        assert window._bubble_timer_ms == 0
        assert window._bubble_queue == []

@pytest.mark.fast
def test_input_submission_clears_queue(app):
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"):
        window = PetWindow(opencode_enabled=False, initial_state={"first_run_done": True})
        window._bubble_queue.clear()
        window._show_bubble("first")
        window._show_bubble("queued")
        window._input_field.setText("!memories")
        window._on_input_submitted()
        assert window._bubble_queue == []

@pytest.mark.fast
def test_mouse_press_on_pet_clears_queue(app):
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"):
        window = PetWindow(opencode_enabled=False, initial_state={"first_run_done": True})
        window._bubble_queue.clear()
        window._show_bubble("first")
        window._show_bubble("queued")
        from PyQt6.QtCore import QPointF, Qt, QEvent
        from PyQt6.QtGui import QMouseEvent
        local = QPointF(window._pet_x + 10, window._pet_y + 10)
        event = QMouseEvent(QEvent.Type.MouseButtonPress, local, local,
                            Qt.MouseButton.LeftButton,
                            Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        window.mousePressEvent(event)
        assert window._bubble_text == ""
        assert window._bubble_queue == []

@pytest.mark.fast
def test_onboarding_bubbles_skipped_if_first_run_done(app):
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"):
        window = PetWindow(opencode_enabled=True, skill_ready=True, initial_state={"first_run_done": True})
        assert len(window._bubble_queue) == 0

@pytest.mark.fast
def test_global_hotkey_action(app):
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"):
        window = PetWindow(opencode_enabled=True)
        window.show = MagicMock()
        window.raise_ = MagicMock()
        window.activateWindow = MagicMock()
        window._show_input_field = MagicMock()
        
        window._on_global_hotkey()
        
        window.show.assert_called_once()
        window.raise_.assert_called_once()
        window.activateWindow.assert_called_once()
        window._show_input_field.assert_called_once()

@pytest.mark.fast
def test_pin_behavior(app):
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"):
        window = PetWindow(opencode_enabled=False)
        window._pinned = True
        
        # Wander should not be due
        ctx = window._build_fsm_context()
        assert ctx.wander_due is False
        
        # Apply physics should return early for states other than DRAGGED/FALLING
        old_x = window._pet_x
        window._wander_target_x = 500
        window._apply_physics(PetState.PERIMETER, 33)
        assert window._pet_x == old_x  # No change

@pytest.mark.fast
def test_recall_memory(app, tmp_path):
    mock_firebase = MagicMock()
    mock_firebase.load_current_brain.return_value = {}
    mock_firebase.read_local_diary.return_value = None
    mock_firebase.fetch_all_diary_entries.return_value = []
    mock_firebase.write_local_diary = MagicMock()
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
            mock_dialog_instance = MagicMock()
            mock_dialog.return_value = mock_dialog_instance
            window._on_recall_memory()
            
            mock_dialog.assert_called_once()
            content_callable = mock_dialog.call_args[0][1]
            content = content_callable()
            assert "TestUser" in content
            assert "Python" in content
            mock_dialog_instance.exec.assert_called_once()
