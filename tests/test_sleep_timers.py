"""Tests for deferred trigger handling during SLEEP state.

Note: Sleep timer accumulation and joke backoff logic has moved to
BehaviorController (tested in test_behavior_controller.py). These tests
verify the remaining PetWindow-specific SLEEP guards.
"""
from unittest.mock import MagicMock, patch
from src.pet_window import PetWindow
from src.pet_fsm import PetState


def _make_pw():
    pw = MagicMock(spec=PetWindow)
    pw._fsm = MagicMock()
    pw._current_apm = 0
    pw._idle_seconds = 0
    pw._deferred_trigger_params = None
    pw._opencode_worker = None
    pw.strands_worker = None
    pw._zombie_workers = set()
    pw._dispatch_trigger = MagicMock()
    return pw


def test_deferred_trigger_dropped_during_sleep():
    pw = _make_pw()
    pw._fsm.current_state = PetState.SLEEP
    pw._deferred_trigger_params = {"mode": "active_chat", "apm": 10}

    PetWindow._fire_deferred_trigger(pw)

    assert pw._deferred_trigger_params is None
    pw._dispatch_trigger.assert_not_called()


def test_deferred_trigger_passes_when_not_sleeping():
    pw = _make_pw()
    pw._fsm.current_state = PetState.IDLE
    pw._deferred_trigger_params = {"mode": "active_chat", "apm": 10, "is_autonomous": True}

    PetWindow._fire_deferred_trigger(pw)

    pw._dispatch_trigger.assert_called_once()
    assert pw._deferred_trigger_params is None


def test_deferred_trigger_discards_on_flow_state():
    pw = _make_pw()
    pw._fsm.current_state = PetState.IDLE
    pw._current_apm = 100
    pw._deferred_trigger_params = {"mode": "active_chat", "apm": 10, "is_autonomous": True}
    pw._opencode_worker = MagicMock()
    pw._opencode_worker.isRunning.return_value = True

    PetWindow._fire_deferred_trigger(pw)

    pw._dispatch_trigger.assert_not_called()
    # Worker should NOT be added to zombie set because apm > 80
    assert len(pw._zombie_workers) == 0
