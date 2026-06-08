"""Tests for Dynamic Global Cooldown."""
import time
import pytest
from unittest.mock import MagicMock, patch
from src.pet_window import PetWindow
from src.pet_fsm import PetState


class TestDynamicGCD:
    def setup_method(self):
        with patch.object(PetWindow, '__init__', lambda self, *a, **kw: None):
            self.pw = PetWindow.__new__(PetWindow)
            self.pw._gcd_expiry_timestamp = 0.0
            self.pw._bubble_text = ""
            self.pw._bubble_timer_ms = 0
            self.pw._bubble_queue = []
            self.pw._tts = MagicMock()
            self.pw._fsm = MagicMock()
            self.pw._fsm.current_state = PetState.IDLE
            self.pw._last_mode = "test"
            self.pw._last_daemon_action = "idle"
            self.pw.interaction_count = 0
            self.pw._history = MagicMock()
            self.pw._log_thought = MagicMock()
            self.pw._show_bubble = MagicMock()

    def test_gcd_set_on_dialogue(self):
        item = {"dialogue": "Hello world", "thought": "test"}
        self.pw._dispatch_structured(item)
        assert self.pw._gcd_expiry_timestamp > time.time()

    def test_gcd_formula_base_plus_length(self):
        item = {"dialogue": "x" * 30, "thought": "test"}  # 30 chars = +1s
        before = time.time()
        self.pw._dispatch_structured(item)
        expected_min = before + 8.0 + 1.0  # 9 seconds
        assert self.pw._gcd_expiry_timestamp >= expected_min - 0.1

    def test_no_gcd_on_empty_dialogue(self):
        item = {"dialogue": "", "thought": "test"}
        self.pw._dispatch_structured(item)
        assert self.pw._gcd_expiry_timestamp == 0.0

    def test_gcd_replaces_thinking_state(self):
        self.pw._fsm.current_state = PetState.THINKING
        item = {"dialogue": "test", "thought": ""}
        self.pw._dispatch_structured(item)
        self.pw._fsm.transition_to.assert_called_with(PetState.IDLE)
