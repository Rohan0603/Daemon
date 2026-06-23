"""Tests for _trigger_boredom_fsm behavior."""
import pytest
from unittest.mock import MagicMock, patch
from src.pet_window import PetWindow
from src.pet_fsm import PetState

class TestTriggerBoredomFsm:
    def setup_method(self):
        with patch.object(PetWindow, '__init__', lambda self, *a, **kw: None):
            self.pw = PetWindow.__new__(PetWindow)
            self.pw._boredom_timer_ms = 0
            self.pw._autonomous_query_pending = False
            self.pw._opencode_enabled = True
            self.pw._current_apm = 0
            self.pw._idle_seconds = 100
            self.pw._boredom_tick_count = 0
            self.pw._response_manager = MagicMock()
            self.pw._response_manager.draw.return_value = [{"dialogue": "test", "action": "idle", "target_x": 0}]
            self.pw._dispatch_structured = MagicMock()
            self.pw._last_context_snapshot = "mock_hash"
            self.pw._fsm = MagicMock()
            self.pw._fsm.current_state = PetState.IDLE
            self.pw._on_output_displayed = MagicMock()

    @patch('src.ui.pet_window.get_active_window_title')
    def test_triggers_draw_and_dispatch(self, mock_window):
        mock_window.return_value = "test"
        self.pw._trigger_boredom_query()
        self.pw._response_manager.draw.assert_called()
        self.pw._dispatch_structured.assert_called_once()

    @patch('src.ui.pet_window.get_active_window_title')
    def test_no_api_when_pending(self, mock_window):
        mock_window.return_value = "test"
        self.pw._autonomous_query_pending = True
        self.pw._trigger_boredom_query()
        self.pw._dispatch_structured.assert_not_called()
