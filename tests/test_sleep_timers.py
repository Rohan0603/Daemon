"""Tests for deferred trigger handling during SLEEP state.

Note: Sleep timer accumulation and joke backoff logic has moved to
BehaviorController (tested in test_behavior_controller.py). These tests
verify the remaining PetWindow-specific SLEEP guards.
"""
import pytest
from unittest.mock import MagicMock, patch
from src.pet_window import PetWindow
from src.pet_fsm import PetState


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
