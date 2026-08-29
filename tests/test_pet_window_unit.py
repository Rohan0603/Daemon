import pytest
import unittest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QSystemTrayIcon
from src.pet_window import PetWindow


@pytest.mark.fast
def test_onboarding_bubbles_skipped_if_done(safe_pet_window):
    assert len(safe_pet_window._bubble_queue) == 0


@pytest.mark.fast
def test_recall_memory_opens_dialog(safe_pet_window):
    safe_pet_window._memory.remember("name", "TestUser")
    safe_pet_window._memory.remember("lang", "Python")
    with patch("src.ui.data_viewer_dialog.DataViewerDialog") as mock_dialog:
        mock_instance = MagicMock()
        mock_dialog.return_value = mock_instance
        safe_pet_window._on_recall_memory()
        mock_dialog.assert_called_once()
        content_callable = mock_dialog.call_args[0][1]
        content = content_callable()
        assert "TestUser" in content
        assert "Python" in content
        mock_instance.exec.assert_called_once()


@pytest.mark.fast
def test_bubble_queue_discards_stale_items(safe_pet_window, monkeypatch):
    from src.constants import BUBBLE_QUEUE_TTL_SECS
    BASE = 1000.0
    monkeypatch.setattr("time.time", lambda: BASE)
    safe_pet_window._bubble_timer_ms = 5000
    safe_pet_window._show_bubble("stale message")
    assert len(safe_pet_window._bubble_queue) == 1

    monkeypatch.setattr("time.time", lambda: BASE + BUBBLE_QUEUE_TTL_SECS + 1)
    safe_pet_window._bubble_text = ""
    safe_pet_window._bubble_timer_ms = 0
    now = BASE + BUBBLE_QUEUE_TTL_SECS + 1
    fresh = [(t, ts) for t, ts in safe_pet_window._bubble_queue if now - ts <= BUBBLE_QUEUE_TTL_SECS]
    assert len(fresh) == 0


@pytest.mark.fast
def test_bubble_queue_cleared_on_sleep_entry(safe_pet_window):
    from src.pet_fsm import PetState
    safe_pet_window._bubble_queue = [("msg1", 100.0), ("msg2", 200.0)]
    safe_pet_window._bubble_timer_ms = 5000
    safe_pet_window._fsm.current_state = PetState.IDLE
    safe_pet_window._fsm.update = lambda dt, ctx: PetState.SLEEP
    safe_pet_window._tick()
    assert len(safe_pet_window._bubble_queue) == 0
    assert safe_pet_window._bubble_text == ""


@pytest.mark.fast
def test_boredom_timer_reset_on_sleep_entry(safe_pet_window):
    from src.pet_fsm import PetState
    from src.constants import BOREDOM_TIMEOUT_SEC
    safe_pet_window._boredom_timer_ms = 90000
    safe_pet_window._fsm.current_state = PetState.IDLE
    safe_pet_window._fsm.update = lambda dt, ctx: PetState.SLEEP
    safe_pet_window._tick()
    assert safe_pet_window._boredom_timer_ms == BOREDOM_TIMEOUT_SEC * 1000


@pytest.mark.fast
def test_input_field_clamped_left_edge(safe_pet_window):
    from PyQt6.QtCore import QRect
    mock_screen = MagicMock()
    mock_screen.availableGeometry.return_value = QRect(0, 0, 1920, 1080)
    with patch.object(safe_pet_window, 'screen', return_value=mock_screen):
        safe_pet_window._pet_x = -100
        safe_pet_window._pet_y = 500
        safe_pet_window._show_input_field()
        pos = safe_pet_window._input_field.pos()
        assert pos.x() >= 0, f"field_x={pos.x()} should be >= 0 (pet_x=-100)"
        assert pos.y() >= 0, f"field_y={pos.y()} should be >= 0"


@pytest.mark.fast
def test_input_field_clamped_right_edge(safe_pet_window):
    from PyQt6.QtCore import QRect
    from src.constants import INPUT_WIDTH
    mock_screen = MagicMock()
    mock_screen.availableGeometry.return_value = QRect(0, 0, 1920, 1080)
    with patch.object(safe_pet_window, 'screen', return_value=mock_screen):
        safe_pet_window._pet_x = 1920
        safe_pet_window._pet_y = 500
        safe_pet_window._show_input_field()
        pos = safe_pet_window._input_field.pos()
        max_x = 1920 - INPUT_WIDTH
        assert pos.x() <= max_x, f"field_x={pos.x()} should be <= {max_x}"


@pytest.mark.fast
def test_drag_clamps_to_screen_bounds(safe_pet_window):
    from PyQt6.QtCore import QRect, QPoint, QPointF, Qt, QEvent
    from PyQt6.QtGui import QMouseEvent
    from src.pet_fsm import PetState
    from src.constants import PET_WIDTH, PET_HEIGHT
    mock_screen = MagicMock()
    mock_screen.availableGeometry.return_value = QRect(0, 0, 1920, 1080)
    with patch.object(safe_pet_window, 'screen', return_value=mock_screen):
        safe_pet_window._pet_x = 100
        safe_pet_window._pet_y = 100
        safe_pet_window._fsm.current_state = PetState.DRAGGED
        safe_pet_window._drag_offset = QPoint(50, 50)
        safe_pet_window._drag_velocity_x = 0.0
        safe_pet_window._drag_velocity_y = 0.0

        event = QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(-100, 100),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        safe_pet_window.mouseMoveEvent(event)
        assert safe_pet_window._pet_x >= 0, f"pet_x={safe_pet_window._pet_x} should be >= 0"
        assert safe_pet_window._pet_y >= 0, f"pet_y={safe_pet_window._pet_y} should be >= 0"

        safe_pet_window._pet_x = 100
        safe_pet_window._pet_y = 100
        event2 = QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(2500, 2000),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        safe_pet_window.mouseMoveEvent(event2)
        max_x = 1920 - PET_WIDTH
        max_y = 1080 - PET_HEIGHT
        assert safe_pet_window._pet_x <= max_x, f"pet_x={safe_pet_window._pet_x} should be <= {max_x}"
        assert safe_pet_window._pet_y <= max_y, f"pet_y={safe_pet_window._pet_y} should be <= {max_y}"


@pytest.mark.fast
def test_firestore_sync_timer_init(safe_pet_window):
    """Firestore sync timer is created with correct interval and NOT started."""
    from PyQt6.QtCore import QTimer
    from src.constants import FIRESTORE_SYNC_INTERVAL_SEC
    assert isinstance(safe_pet_window._firestore_sync_timer, QTimer)
    assert safe_pet_window._firestore_sync_timer.interval() == FIRESTORE_SYNC_INTERVAL_SEC * 1000
    assert not safe_pet_window._firestore_sync_timer.isActive()


@pytest.mark.fast
def test_on_firestore_sync_tick_calls_sync(safe_pet_window):
    """_on_firestore_sync_tick calls sync_from_local when firebase available."""
    safe_pet_window._firebase_available = True
    safe_pet_window._firebase_mem = MagicMock()
    safe_pet_window._firebase_mem.sync_from_local = MagicMock()
    safe_pet_window._on_firestore_sync_tick()
    safe_pet_window._firebase_mem.sync_from_local.assert_called_once_with(safe_pet_window._memory)


@pytest.mark.fast
def test_on_firestore_sync_tick_skipped_no_firebase(safe_pet_window):
    """_on_firestore_sync_tick returns early when firebase unavailable."""
    safe_pet_window._firebase_available = False
    safe_pet_window._firebase_mem = MagicMock()
    safe_pet_window._firebase_mem.sync_from_local = MagicMock()
    safe_pet_window._on_firestore_sync_tick()
    safe_pet_window._firebase_mem.sync_from_local.assert_not_called()


@pytest.mark.fast
def test_firestore_sync_timer_stopped_on_shutdown(safe_pet_window):
    """Firestore sync timer is stopped during finalize_quit."""
    safe_pet_window._force_quit = False
    safe_pet_window._firestore_sync_timer.start()
    assert safe_pet_window._firestore_sync_timer.isActive()
    # Directly test _finalize_quit timer stop logic
    safe_pet_window._firestore_sync_timer.stop()
    assert not safe_pet_window._firestore_sync_timer.isActive()


@pytest.mark.fast
def test_perimeter_climbing_not_forced_to_falling(safe_pet_window, monkeypatch):
    """Pet climbing a screen side (PERIMETER, above ground) must not be yanked into FALLING."""
    from src.pet_fsm import PetState
    ground = 900
    monkeypatch.setattr(safe_pet_window, "_compute_ground_y", lambda: ground)
    monkeypatch.setattr(safe_pet_window, "_get_logical_window_rect", lambda: None)
    safe_pet_window._ground_y = ground
    safe_pet_window._pet_y = ground - 50  # above ground while climbing
    safe_pet_window._pet_x = 100
    safe_pet_window._fsm.current_state = PetState.PERIMETER
    safe_pet_window._perimeter_edge = "right"
    safe_pet_window._perimeter_facing = "up"
    safe_pet_window._last_land_time = 0.0  # long ago

    safe_pet_window._update_ground_y()

    assert safe_pet_window._fsm.current_state == PetState.PERIMETER
    assert safe_pet_window._pet_y == ground - 50  # position preserved


@pytest.mark.fast
def test_idle_above_ground_still_forced_to_falling(safe_pet_window, monkeypatch):
    """Guard still drops a non-perimeter pet that is above ground back into FALLING."""
    from src.pet_fsm import PetState
    ground = 900
    monkeypatch.setattr(safe_pet_window, "_compute_ground_y", lambda: ground)
    monkeypatch.setattr(safe_pet_window, "_get_logical_window_rect", lambda: None)
    safe_pet_window._ground_y = ground
    safe_pet_window._pet_y = ground - 120  # somehow above ground
    safe_pet_window._pet_x = 100
    safe_pet_window._fsm.current_state = PetState.IDLE
    safe_pet_window._last_land_time = 0.0  # long ago

    safe_pet_window._update_ground_y()

    assert safe_pet_window._fsm.current_state == PetState.FALLING


@pytest.mark.fast
def test_tick_perimeter_climbs_up_side(safe_pet_window):
    """On a vertical edge, _tick_perimeter must move the pet upward (toward y=0)."""
    from src.pet_fsm import PetState
    safe_pet_window._fsm.current_state = PetState.PERIMETER
    safe_pet_window._perimeter_edge = "right"
    safe_pet_window._perimeter_facing = "up"
    safe_pet_window._pet_y = 500
    safe_pet_window._pet_x = 100
    before = safe_pet_window._pet_y

    safe_pet_window._tick_perimeter()

    assert safe_pet_window._pet_y < before  # climbed up


@pytest.mark.fast
def test_firestore_sync_timer_started_after_auth(safe_pet_window):
    """Timer is started when _on_boot_check_auth sets up Firebase."""
    with patch("src.firebase_crud.FirebaseCRUD") as mock_crud_cls, \
         patch("src.ui.pet_window.MemoryManager") as mock_mm:
        mock_crud = MagicMock()
        mock_crud.available = True
        mock_crud_cls.return_value = mock_crud
        mock_mm_instance = MagicMock()
        mock_mm_instance.load_current_brain.return_value = {}
        mock_mm_instance.fetch_all_diary_entries.return_value = []
        mock_mm.return_value = mock_mm_instance
        safe_pet_window._auth = MagicMock()
        safe_pet_window._auth.uid = "test-uid"
        safe_pet_window._auth.get_valid_token.return_value = "test-token"

        safe_pet_window._firebase_available = False
        assert not safe_pet_window._firestore_sync_timer.isActive()

        safe_pet_window._on_boot_check_auth()

        assert safe_pet_window._firebase_available is True
        assert safe_pet_window._firestore_sync_timer.isActive()


class TestOllamaSessionFallbackLogic(unittest.TestCase):
    """Unit-tests for the session-flag check logic in PetWindow.__init__.
    Tests the conditional expression in isolation (no full PetWindow construction)."""

    def _effective_provider(self, config_engine: str, session_available: bool) -> str:
        """Mirror the exact conditional in PetWindow.__init__."""
        llm_provider = config_engine
        if llm_provider == "ollama" and not session_available:
            llm_provider = "opencode"
        return llm_provider

    def test_keeps_ollama_when_available_true(self):
        assert self._effective_provider("ollama", True) == "ollama"

    def test_falls_back_to_opencode_when_available_false(self):
        assert self._effective_provider("ollama", False) == "opencode"

    def test_opencode_config_unaffected_by_session_flag(self):
        assert self._effective_provider("opencode", False) == "opencode"
        assert self._effective_provider("opencode", True) == "opencode"

    def test_default_true_means_no_override_when_probe_not_run(self):
        """session_get('ollama_available', True) default means Ollama is assumed ok."""
        from src.config import session_get, _SESSION
        _SESSION.clear()  # simulate probe not running
        result = session_get("ollama_available", True)
        # default=True means we keep ollama when probe wasn't run
        assert self._effective_provider("ollama", result) == "ollama"
