"""Tests for _master_tick delegation to BehaviorController.

Note: The priority tree logic has moved to BehaviorController
(tested in test_behavior_controller.py). These tests verify that
_master_tick correctly delegates and handles errors.
"""
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


class TestMasterTickDelegation:
    def setup_method(self):
        self._pw_app = app()
        from PyQt6.QtWidgets import QWidget
        def mock_init(self, *a, **kw):
            QWidget.__init__(self)
        with patch.object(PetWindow, '__init__', mock_init):
            self.pw = PetWindow()
            self.pw._fsm = MagicMock()
            self.pw._behavior = MagicMock()
            self.pw._idle_seconds = 0
            self.pw._last_master_tick_time = time.monotonic() - 1.0

    def test_delegates_to_behavior_tick(self):
        self.pw._master_tick()
        self.pw._behavior.tick.assert_called_once()

    def test_syncs_idle_seconds(self):
        self.pw._idle_seconds = 42.5
        self.pw._master_tick()
        self.pw._behavior.set_idle_seconds.assert_called_once_with(42.5)

    def test_updates_last_master_tick_time(self):
        old = self.pw._last_master_tick_time
        self.pw._master_tick()
        assert self.pw._last_master_tick_time != old

    def test_behavior_tick_receives_delta(self):
        self.pw._master_tick()
        args, _ = self.pw._behavior.tick.call_args
        dt = args[0]
        assert 0.5 < dt < 2.0  # Should be ~1s with tolerance

    def test_exception_in_behavior_bubbles_up(self):
        self.pw._behavior.tick.side_effect = ValueError("boom")
        with pytest.raises(ValueError):
            self.pw._master_tick()
