"""Integration test: Full behavioral tick cycle."""
import time
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from src.pet_window import PetWindow
from src.pet_fsm import PetState


class TestBehaviorIntegration:
    def setup_method(self):
        with patch.object(PetWindow, '__init__', lambda self, *a, **kw: None):
            self.pw = PetWindow.__new__(PetWindow)
            self.pw._chat_timer_sec = 0
            self.pw._joke_timer_sec = 0
            self.pw._boredom_tick_count = 0
            self.pw._gcd_expiry_timestamp = 0.0
            self.pw._chattiness = 1.0
            self.pw._current_apm = 0
            self.pw._idle_seconds = 0
            self.pw._opencode_enabled = True
            self.pw._autonomous_query_pending = False
            self.pw._fsm = MagicMock()
            self.pw._fsm.current_state = PetState.IDLE
            self.pw._response_manager = MagicMock()
            self.pw._response_manager.draw.return_value = [{"dialogue": "test", "action": "idle"}]
            self.pw._typing_buffer = MagicMock()
            self.pw._typing_buffer.get_context.return_value = ""
            self.pw._last_active_window = ""
            self.pw._last_typing_snapshot = ""
            self.pw._dispatch_structured = MagicMock()
            self.pw._dispatch_trigger = MagicMock()
            self.pw._show_bubble = MagicMock()
            self.pw._history = MagicMock()
            self.pw._log_thought = MagicMock()
            self.pw._last_mode = "test"
            self.pw._last_daemon_action = "idle"
            self.pw.interaction_count = 0
            self.pw._bubble_text = ""
            self.pw._bubble_timer_ms = 0
            self.pw._bubble_queue = []
            self.pw._tts = MagicMock()
            self.pw._calculate_joke_modifier = MagicMock(return_value=1.0)
            self.pw._has_significant_delta = MagicMock(return_value=False)
            self.pw._trigger_chat = MagicMock()
            self.pw._trigger_joke = MagicMock()
            self.pw._trigger_boredom_fsm = MagicMock()
            # Exponential backoff fields
            self.pw._last_context_snapshot = None
            self.pw._idle_backoff_seconds = 0.0
            self.pw._base_boredom_interval = 30
            self.pw._max_idle_backoff = 300
            self.pw._last_boredom_fsm_time = 0.0
            self.pw._is_context_stable = MagicMock(return_value=True)

    @patch('src.pet_window.get_active_window_title')
    def test_full_flow_state_silence(self, mock_window):
        """APM > 80 should silence all autonomous actions."""
        mock_window.return_value = "IDE"
        self.pw._current_apm = 85
        self.pw._chat_timer_sec = 100
        self.pw._joke_timer_sec = 100
        self.pw._has_significant_delta.return_value = True
        self.pw._master_tick()
        self.pw._trigger_chat.assert_not_called()
        self.pw._trigger_joke.assert_not_called()

    @patch('src.pet_window.get_active_window_title')
    def test_full_chat_reaction(self, mock_window):
        """Chat timer + delta should trigger chat."""
        mock_window.return_value = "Terminal"
        self.pw._chat_timer_sec = 25
        self.pw._has_significant_delta.return_value = True
        self.pw._master_tick()
        self.pw._trigger_chat.assert_called_once()

    @patch('src.pet_window.get_active_window_title')
    def test_full_joke_reaction(self, mock_window):
        """Joke timer + low APM should trigger joke."""
        mock_window.return_value = ""
        self.pw._joke_timer_sec = 60
        self.pw._current_apm = 5
        self.pw._master_tick()
        self.pw._trigger_joke.assert_called_once()

    @patch('src.pet_window.get_active_window_title')
    def test_full_boredom_reaction(self, mock_window):
        """Idle >= 60 + APM 0 should trigger boredom FSM."""
        mock_window.return_value = ""
        self.pw._idle_seconds = 60
        self.pw._current_apm = 0
        self.pw._master_tick()
        self.pw._trigger_boredom_fsm.assert_called_once()

    @patch('src.pet_window.get_active_window_title')
    def test_gcd_blocks_everything(self, mock_window):
        """Active GCD should block all triggers."""
        mock_window.return_value = "IDE"
        self.pw._gcd_expiry_timestamp = time.time() + 100
        self.pw._chat_timer_sec = 100
        self.pw._joke_timer_sec = 100
        self.pw._has_significant_delta.return_value = True
        self.pw._master_tick()
        self.pw._trigger_chat.assert_not_called()
        self.pw._trigger_joke.assert_not_called()
        self.pw._trigger_boredom_fsm.assert_not_called()
