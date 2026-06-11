"""Tests for _trigger_chat behavior."""
import pytest
from unittest.mock import MagicMock, patch
from src.pet_window import PetWindow


class TestTriggerChat:
    def setup_method(self):
        with patch.object(PetWindow, '__init__', lambda self, *a, **kw: None):
            self.pw = PetWindow.__new__(PetWindow)
            self.pw._chat_timer_sec = 100
            self.pw._response_manager = MagicMock()
            self.pw._response_manager.draw.return_value = [{"dialogue": "test", "action": "idle"}]
            self.pw._autonomous_query_pending = False
            self.pw._opencode_enabled = True
            self.pw._current_apm = 20
            self.pw._idle_seconds = 0
            self.pw._typing_buffer = MagicMock()
            self.pw._typing_buffer.get_context.return_value = ""
            self.pw._dispatch_structured = MagicMock()
            self.pw._dispatch_trigger = MagicMock()
            self.pw._last_context_snapshot = None

    @patch('src.pet_window.get_active_window_title')
    def test_resets_timer(self, mock_window):
        mock_window.return_value = "test"
        self.pw._trigger_chat()
        assert self.pw._chat_timer_sec == 0

    @patch('src.pet_window.get_active_window_title')
    def test_draws_local_reaction(self, mock_window):
        mock_window.return_value = "test"
        self.pw._trigger_chat()
        self.pw._response_manager.draw.assert_called_with("typing_reaction", current_context_hash=None)

    @patch('src.pet_window.get_active_window_title')
    def test_dispatches_structured(self, mock_window):
        mock_window.return_value = "test"
        self.pw._trigger_chat()
        self.pw._dispatch_structured.assert_called_once()

    @patch('src.pet_window.get_active_window_title')
    def test_dispatches_trigger(self, mock_window):
        mock_window.return_value = "test"
        self.pw._trigger_chat()
        self.pw._dispatch_trigger.assert_called_once()
