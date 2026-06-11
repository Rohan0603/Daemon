"""Tests for _master_tick behavioral loop."""
import time
import pytest
from unittest.mock import MagicMock, patch
from src.pet_window import PetWindow
from src.pet_fsm import PetState


def app():
    import sys
    from PyQt6.QtWidgets import QApplication
    _app = QApplication.instance()
    if _app is None:
        _app = QApplication(sys.argv)
    return _app


class TestMasterTick:
    def setup_method(self):
        self._pw_app = app()  # ensure QApplication exists
        from PyQt6.QtWidgets import QWidget
        def mock_init(self, *a, **kw):
            QWidget.__init__(self)
        with patch.object(PetWindow, '__init__', mock_init):
            self.pw = PetWindow()
            self.pw._emotion_timer_sec = 0
            self.pw._last_evaluated_window = ""
            self.pw._window_switch_count = 0
            self.pw._fsm = MagicMock()
            self.pw._fsm.current_state = PetState.IDLE
            self.pw._chat_timer_sec = 0
            self.pw._joke_timer_sec = 0
            self.pw._gcd_expiry_timestamp = 0.0
            self.pw._chattiness = 1.0
            self.pw._current_apm = 0
            self.pw._idle_seconds = 0
            self.pw._has_significant_delta = MagicMock(return_value=False)
            self.pw._trigger_chat = MagicMock()
            self.pw._trigger_joke = MagicMock()
            self.pw._trigger_boredom_fsm = MagicMock()
            self.pw._calculate_joke_modifier = MagicMock(return_value=1.0)
            # Exponential backoff fields
            self.pw._last_context_snapshot = None
            self.pw._idle_backoff_seconds = 0.0
            self.pw._base_boredom_interval = 30
            self.pw._max_idle_backoff = 300
            self.pw._last_boredom_fsm_time = time.time()
            self.pw._boredom_timer_ms = 30000
            self.pw._boredom_tick_count = 0
            self.pw._is_context_stable = MagicMock(return_value=True)

    def test_increments_timers(self):
        self.pw._master_tick()
        assert self.pw._chat_timer_sec == 1
        assert self.pw._joke_timer_sec == 1

    def test_gcd_blocks_all(self):
        self.pw._gcd_expiry_timestamp = time.time() + 100
        self.pw._master_tick()
        self.pw._trigger_chat.assert_not_called()
        self.pw._trigger_joke.assert_not_called()

    def test_flow_state_silence(self):
        self.pw._current_apm = 85
        self.pw._master_tick()
        self.pw._trigger_chat.assert_not_called()
        self.pw._trigger_joke.assert_not_called()

    def test_chat_fires_on_delta(self):
        self.pw._chat_timer_sec = 25  # >= threshold
        self.pw._has_significant_delta.return_value = True
        self.pw._master_tick()
        self.pw._trigger_chat.assert_called_once()

    def test_joke_fires_on_low_apm(self):
        self.pw._joke_timer_sec = 60  # >= threshold
        self.pw._current_apm = 5  # < 20
        self.pw._master_tick()
        self.pw._trigger_joke.assert_called_once()

    def test_boredom_fires(self):
        self.pw._idle_seconds = 60
        self.pw._current_apm = 0
        self.pw._master_tick()
        self.pw._trigger_boredom_fsm.assert_called_once()
