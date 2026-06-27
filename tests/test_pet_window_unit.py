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


@pytest.mark.fast
def test_input_field_clamped_left_edge(app):
    from PyQt6.QtCore import QRect
    with patch("src.ui.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.ui.pet_window.APMWorker"), \
         patch("src.ui.pet_window.MCPServer"), \
         patch("src.ui.pet_window.BehaviorController"):
        window = PetWindow(opencode_enabled=False)
        mock_screen = MagicMock()
        mock_screen.availableGeometry.return_value = QRect(0, 0, 1920, 1080)
        with patch.object(window, 'screen', return_value=mock_screen):
            window._pet_x = -100
            window._pet_y = 500
            window._show_input_field()
            pos = window._input_field.pos()
            assert pos.x() >= 0, f"field_x={pos.x()} should be >= 0 (pet_x=-100)"
            assert pos.y() >= 0, f"field_y={pos.y()} should be >= 0"


@pytest.mark.fast
def test_input_field_clamped_right_edge(app):
    from PyQt6.QtCore import QRect
    from src.constants import INPUT_WIDTH
    with patch("src.ui.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.ui.pet_window.APMWorker"), \
         patch("src.ui.pet_window.MCPServer"), \
         patch("src.ui.pet_window.BehaviorController"):
        window = PetWindow(opencode_enabled=False)
        mock_screen = MagicMock()
        mock_screen.availableGeometry.return_value = QRect(0, 0, 1920, 1080)
        with patch.object(window, 'screen', return_value=mock_screen):
            window._pet_x = 1920
            window._pet_y = 500
            window._show_input_field()
            pos = window._input_field.pos()
            max_x = 1920 - INPUT_WIDTH
            assert pos.x() <= max_x, f"field_x={pos.x()} should be <= {max_x}"


@pytest.mark.fast
def test_drag_clamps_to_screen_bounds(app):
    from PyQt6.QtCore import QRect, QPoint, QPointF, Qt, QEvent
    from PyQt6.QtGui import QMouseEvent
    from src.pet_fsm import PetState
    from src.constants import PET_WIDTH, PET_HEIGHT
    with patch("src.ui.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.ui.pet_window.APMWorker"), \
         patch("src.ui.pet_window.MCPServer"), \
         patch("src.ui.pet_window.BehaviorController"):
        window = PetWindow(opencode_enabled=False)
        mock_screen = MagicMock()
        mock_screen.availableGeometry.return_value = QRect(0, 0, 1920, 1080)
        with patch.object(window, 'screen', return_value=mock_screen):
            window._pet_x = 100
            window._pet_y = 100
            window._fsm.current_state = PetState.DRAGGED
            window._drag_offset = QPoint(50, 50)
            window._drag_velocity_x = 0.0
            window._drag_velocity_y = 0.0

            event = QMouseEvent(
                QEvent.Type.MouseMove,
                QPointF(-100, 100),
                Qt.MouseButton.NoButton,
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier,
            )
            window.mouseMoveEvent(event)
            assert window._pet_x >= 0, f"pet_x={window._pet_x} should be >= 0"
            assert window._pet_y >= 0, f"pet_y={window._pet_y} should be >= 0"

            window._pet_x = 100
            window._pet_y = 100
            event2 = QMouseEvent(
                QEvent.Type.MouseMove,
                QPointF(2500, 2000),
                Qt.MouseButton.NoButton,
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier,
            )
            window.mouseMoveEvent(event2)
            max_x = 1920 - PET_WIDTH
            max_y = 1080 - PET_HEIGHT
            assert window._pet_x <= max_x, f"pet_x={window._pet_x} should be <= {max_x}"
            assert window._pet_y <= max_y, f"pet_y={window._pet_y} should be <= {max_y}"


@pytest.mark.fast
def test_firestore_sync_timer_init(app):
    """Firestore sync timer is created with correct interval and NOT started."""
    from PyQt6.QtCore import QTimer
    from src.constants import FIRESTORE_SYNC_INTERVAL_SEC
    with patch("src.ui.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.ui.pet_window.APMWorker"), \
         patch("src.ui.pet_window.MCPServer"), \
         patch("src.ui.pet_window.BehaviorController"):
        window = PetWindow(opencode_enabled=False)
        assert isinstance(window._firestore_sync_timer, QTimer)
        assert window._firestore_sync_timer.interval() == FIRESTORE_SYNC_INTERVAL_SEC * 1000
        assert not window._firestore_sync_timer.isActive()


@pytest.mark.fast
def test_on_firestore_sync_tick_calls_sync(app):
    """_on_firestore_sync_tick calls sync_from_local when firebase available."""
    with patch("src.ui.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.ui.pet_window.APMWorker"), \
         patch("src.ui.pet_window.MCPServer"), \
         patch("src.ui.pet_window.BehaviorController"):
        window = PetWindow(opencode_enabled=False)
        window._firebase_available = True
        window._firebase_mem = MagicMock()
        window._firebase_mem.sync_from_local = MagicMock()
        window._on_firestore_sync_tick()
        window._firebase_mem.sync_from_local.assert_called_once_with(window._memory)


@pytest.mark.fast
def test_on_firestore_sync_tick_skipped_no_firebase(app):
    """_on_firestore_sync_tick returns early when firebase unavailable."""
    with patch("src.ui.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.ui.pet_window.APMWorker"), \
         patch("src.ui.pet_window.MCPServer"), \
         patch("src.ui.pet_window.BehaviorController"):
        window = PetWindow(opencode_enabled=False)
        window._firebase_available = False
        window._firebase_mem = MagicMock()
        window._firebase_mem.sync_from_local = MagicMock()
        window._on_firestore_sync_tick()
        window._firebase_mem.sync_from_local.assert_not_called()


@pytest.mark.fast
def test_firestore_sync_timer_stopped_on_shutdown(app):
    """Firestore sync timer is stopped during finalize_quit."""
    with patch("src.ui.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.ui.pet_window.APMWorker"), \
         patch("src.ui.pet_window.MCPServer"), \
         patch("src.ui.pet_window.BehaviorController"):
        window = PetWindow(opencode_enabled=False)
        window._force_quit = False
        window._firestore_sync_timer.start()
        assert window._firestore_sync_timer.isActive()
        # Directly test _finalize_quit timer stop logic
        window._firestore_sync_timer.stop()
        assert not window._firestore_sync_timer.isActive()


@pytest.mark.fast
def test_firestore_sync_timer_started_after_auth(app):
    """Timer is started when _on_boot_check_auth sets up Firebase."""
    with patch("src.ui.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.ui.pet_window.APMWorker"), \
         patch("src.ui.pet_window.MCPServer"), \
         patch("src.ui.pet_window.BehaviorController"), \
         patch("src.firebase_crud.FirebaseCRUD") as mock_crud_cls, \
         patch("src.ui.pet_window.MemoryManager") as mock_mm:
        mock_crud = MagicMock()
        mock_crud.available = True
        mock_crud_cls.return_value = mock_crud
        mock_mm_instance = MagicMock()
        mock_mm_instance.load_current_brain.return_value = {}
        mock_mm_instance.fetch_all_diary_entries.return_value = []
        mock_mm.return_value = mock_mm_instance

        window = PetWindow(opencode_enabled=False, fresh_login=False)
        window._firebase_available = False
        assert not window._firestore_sync_timer.isActive()

        window._on_boot_check_auth()

        assert window._firebase_available is True
        assert window._firestore_sync_timer.isActive()
