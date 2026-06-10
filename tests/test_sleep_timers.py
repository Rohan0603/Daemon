import pytest
import time
from unittest.mock import MagicMock, patch
from src.pet_window import PetWindow
from src.pet_fsm import PetState


class TestSleepTimers:
    """Verify behavioral timers freeze when FSM is in SLEEP state."""

    def test_joke_timer_freezes_during_sleep(self):
        """_joke_timer_sec must NOT increment while in SLEEP."""
        pw = MagicMock(spec=PetWindow)
        pw._fsm = MagicMock()
        pw._fsm.current_state = PetState.SLEEP
        pw._chat_timer_sec = 0
        pw._joke_timer_sec = 0
        pw._gcd_expiry_timestamp = 0  # not in cooldown
        pw._current_apm = 0
        pw._idle_seconds = 400
        pw._chattiness = 1.0
        pw._has_significant_delta = MagicMock(return_value=False)
        pw._calculate_joke_modifier = MagicMock(return_value=1.0)

        PetWindow._master_tick(pw)

        assert pw._joke_timer_sec == 0, "joke_timer should NOT increment during SLEEP"
        assert pw._chat_timer_sec == 0, "chat_timer should NOT increment during SLEEP"


class TestDeferredTriggerSleep:
    """Verify deferred triggers are dropped when FSM is in SLEEP."""

    def test_deferred_trigger_dropped_during_sleep(self):
        """_fire_deferred_trigger must discard the trigger when sleeping."""
        pw = MagicMock(spec=PetWindow)
        pw._fsm = MagicMock()
        pw._fsm.current_state = PetState.SLEEP
        pw._deferred_trigger_params = {"mode": "active_chat", "apm": 10}
        pw._opencode_worker = None

        PetWindow._fire_deferred_trigger(pw)

        # Should NOT call _dispatch_trigger
        pw._dispatch_trigger.assert_not_called()
        # Should clear the deferred params
        assert pw._deferred_trigger_params is None


class TestJokeBackoff:
    """Verify joke triggers respect exponential backoff."""

    def test_joke_blocked_during_backoff(self):
        """P3 joke must NOT fire when _idle_backoff_seconds exceeds threshold."""
        pw = MagicMock(spec=PetWindow)
        pw._fsm = MagicMock()
        pw._fsm.current_state = PetState.IDLE
        pw._joke_timer_sec = 999  # well past threshold
        pw._current_apm = 5  # < 20, would normally trigger
        pw._chattiness = 1.0
        pw._idle_seconds = 30
        pw._gcd_expiry_timestamp = 0
        pw._chat_timer_sec = 0
        pw._has_significant_delta = MagicMock(return_value=False)
        pw._calculate_joke_modifier = MagicMock(return_value=1.0)
        pw._boredom_timer_ms = 30000
        pw._idle_backoff_seconds = 300  # max backoff reached
        pw._last_boredom_fsm_time = time.time()  # just fired, elapsed = 0
        pw._last_context_snapshot = None
        pw._is_context_stable = MagicMock(return_value=True)
        pw._base_boredom_interval = 30
        pw._max_idle_backoff = 300
        pw._boredom_tick_count = 0
        pw._autonomous_query_pending = False
        pw._opencode_enabled = True

        PetWindow._master_tick(pw)

        # Should NOT have called _trigger_joke because backoff is active
        pw._trigger_joke.assert_not_called()