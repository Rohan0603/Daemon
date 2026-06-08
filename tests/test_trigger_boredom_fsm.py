"""Tests for _trigger_boredom_fsm behavior."""
import pytest
from unittest.mock import MagicMock, patch
from src.pet_window import PetWindow
from src.pet_fsm import PetState


class TestTriggerBoredomFsm:
    def setup_method(self):
        with patch.object(PetWindow, '__init__', lambda self, *a, **kw: None):
            self.pw = PetWindow.__new__(PetWindow)
            self.pw._boredom_tick_count = 0
            self.pw._fsm = MagicMock()
            self.pw._fsm.current_state = PetState.IDLE
            self.pw._opencode_enabled = True
            self.pw._autonomous_query_pending = False
            self.pw._current_apm = 0
            self.pw._idle_seconds = 60
            self.pw._dispatch_trigger = MagicMock()

    @patch('src.pet_window.get_active_window_title')
    def test_transitions_fsm_state(self, mock_window):
        mock_window.return_value = "test"
        self.pw._trigger_boredom_fsm()
        self.pw._fsm.transition_to.assert_called_once()

    @patch('src.pet_window.get_active_window_title')
    def test_increments_tick_count(self, mock_window):
        mock_window.return_value = "test"
        self.pw._trigger_boredom_fsm()
        assert self.pw._boredom_tick_count == 1

    @patch('src.pet_window.get_active_window_title')
    def test_api_every_4th_tick(self, mock_window):
        mock_window.return_value = "test"
        self.pw._boredom_tick_count = 3  # Next tick will be 0
        self.pw._trigger_boredom_fsm()
        self.pw._dispatch_trigger.assert_called_once()

    @patch('src.pet_window.get_active_window_title')
    def test_no_api_on_other_ticks(self, mock_window):
        mock_window.return_value = "test"
        self.pw._boredom_tick_count = 0
        self.pw._trigger_boredom_fsm()
        self.pw._dispatch_trigger.assert_not_called()
