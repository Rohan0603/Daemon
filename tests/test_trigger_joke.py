"""Tests for _trigger_joke behavior."""
import pytest
from unittest.mock import MagicMock, patch
from src.pet_window import PetWindow


class TestTriggerJoke:
    def setup_method(self):
        with patch.object(PetWindow, '__init__', lambda self, *a, **kw: None):
            self.pw = PetWindow.__new__(PetWindow)
            self.pw._joke_timer_sec = 100
            self.pw._autonomous_query_pending = False
            self.pw._opencode_enabled = True
            self.pw._current_apm = 20
            self.pw._idle_seconds = 0
            self.pw._response_manager = MagicMock()
            self.pw._response_manager.draw.return_value = [{"dialogue": "test", "action": "idle", "target_x": 0}]
            self.pw._dispatch_structured = MagicMock()
            self.pw._last_context_snapshot = "mock_hash"
            self.pw._fsm = MagicMock()
            from src.pet_fsm import PetState
            self.pw._fsm.current_state = PetState.IDLE
            self.pw._events = MagicMock()
            self.pw._events = MagicMock()
            self.pw._current_context_hash = "mock_hash"

    @patch('src.pet_window.get_active_window_title')
    def test_resets_timer(self, mock_window):
        mock_window.return_value = "test"
        self.pw._trigger_joke()
        assert self.pw._joke_timer_sec == 0

    @patch('src.pet_window.get_active_window_title')
    def test_dispatches_trigger(self, mock_window):
        mock_window.return_value = "test"
        self.pw._trigger_joke()
        self.pw._response_manager.draw.assert_called_once_with("intel_roast", current_context_hash="mock_hash")
        self.pw._dispatch_structured.assert_called_once()

    @patch('src.pet_window.get_active_window_title')
    def test_no_dispatch_when_pending(self, mock_window):
        mock_window.return_value = "test"
        self.pw._autonomous_query_pending = True
        self.pw._trigger_joke()
        self.pw._response_manager.draw.assert_not_called()

    @patch('src.pet_window.get_active_window_title')
    def test_no_dispatch_when_disabled(self, mock_window):
        mock_window.return_value = "test"
        self.pw._opencode_enabled = False
        self.pw._trigger_joke()
        self.pw._response_manager.draw.assert_not_called()
