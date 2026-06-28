"""Tests for _master_tick delegation to BehaviorController.

Note: The priority tree logic has moved to BehaviorController
(tested in test_behavior_controller.py). These tests verify that
_master_tick correctly delegates and handles errors.
"""
import time
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QWidget


def _make_pw():
    """Build a PetWindow-ish object without touching Qt app."""
    with patch.object(QWidget, '__init__', lambda self, *a, **kw: None):
        from src.pet_window import PetWindow
        pw = PetWindow.__new__(PetWindow)
    pw._fsm = MagicMock()
    pw._behavior = MagicMock()
    pw._idle_seconds = 0
    pw._screen_time_tick = 0
    pw._state_save_tick = 0
    pw._last_master_tick_time = time.monotonic() - 1.0
    return pw


def test_delegates_to_behavior_tick():
    pw = _make_pw()
    pw._master_tick()
    pw._behavior.tick.assert_called_once()


def test_syncs_idle_seconds():
    pw = _make_pw()
    pw._idle_seconds = 42.5
    pw._master_tick()
    pw._behavior.set_idle_seconds.assert_called_once_with(42.5)


def test_updates_last_master_tick_time():
    pw = _make_pw()
    old = pw._last_master_tick_time
    pw._master_tick()
    assert pw._last_master_tick_time != old


def test_behavior_tick_receives_delta():
    pw = _make_pw()
    pw._master_tick()
    args, _ = pw._behavior.tick.call_args
    dt = args[0]
    assert 0.5 < dt < 2.0


def test_exception_in_behavior_bubbles_up():
    pw = _make_pw()
    pw._behavior.tick.side_effect = ValueError("boom")
    try:
        pw._master_tick()
    except ValueError:
        pass
    else:
        raise AssertionError("ValueError did not propagate")
