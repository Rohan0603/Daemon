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
            self.pw._dispatch_trigger = MagicMock()

    @patch('src.pet_window.get_active_window_title')
    def test_resets_timer(self, mock_window):
        mock_window.return_value = "test"
        self.pw._trigger_joke()
        assert self.pw._joke_timer_sec == 0

    @patch('src.pet_window.get_active_window_title')
    def test_dispatches_trigger(self, mock_window):
        mock_window.return_value = "test"
        self.pw._trigger_joke()
        self.pw._dispatch_trigger.assert_called_once()

    @patch('src.pet_window.get_active_window_title')
    def test_no_dispatch_when_pending(self, mock_window):
        mock_window.return_value = "test"
        self.pw._autonomous_query_pending = True
        self.pw._trigger_joke()
        self.pw._dispatch_trigger.assert_not_called()

    @patch('src.pet_window.get_active_window_title')
    def test_no_dispatch_when_disabled(self, mock_window):
        mock_window.return_value = "test"
        self.pw._opencode_enabled = False
        self.pw._trigger_joke()
        self.pw._dispatch_trigger.assert_not_called()
