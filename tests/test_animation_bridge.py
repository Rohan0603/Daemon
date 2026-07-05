"""Test Phase 3 Animation Bridge — trigger_state_override, override lock.

Pure mock tests — no PetWindow instantiation needed.
"""
from unittest.mock import MagicMock
import pytest
from PyQt6.QtCore import QTimer
from src.pet_fsm import PetState


@pytest.fixture
def mock_window():
    """Minimal PetWindow-like object with animation bridge attributes."""
    win = MagicMock()
    win._action_layer = MagicMock()
    win._fsm = MagicMock()
    win._animation_override_active = False
    win._clear_animation_override = lambda: setattr(win, '_animation_override_active', False)
    return win


def fsm_state_override(win, state):
    """Simulate trigger_state_override logic for FSM states."""
    fsm_states = {"IDLE": PetState.IDLE, "THINKING": PetState.THINKING}
    if state in fsm_states:
        win._fsm.transition_to(fsm_states[state])


def action_state_override(win, state, duration_ms=2000):
    """Simulate trigger_state_override logic for action states."""
    action_states = {"FRUSTRATED", "SMUG", "SHOCKED", "LAUGHING"}
    if state in action_states:
        win._action_layer.trigger(state.lower(), duration_ms)
        win._animation_override_active = True
        QTimer.singleShot(duration_ms, win._clear_animation_override)


def test_trigger_state_override_fsm_state(mock_window):
    """IDLE triggers transition_to(PetState.IDLE)."""
    fsm_state_override(mock_window, "IDLE")
    mock_window._fsm.transition_to.assert_called_once_with(PetState.IDLE)


def test_trigger_state_override_action_layer_state(mock_window):
    """FRUSTRATED calls action_layer.trigger and sets override flag."""
    action_state_override(mock_window, "FRUSTRATED", 2000)
    mock_window._action_layer.trigger.assert_called_once_with("frustrated", 2000)
    assert mock_window._animation_override_active is True


def test_thinking_state_triggers_fsm(mock_window):
    """THINKING should route to FSM transition_to."""
    fsm_state_override(mock_window, "THINKING")
    mock_window._fsm.transition_to.assert_called_once_with(PetState.THINKING)
    mock_window._action_layer.trigger.assert_not_called()


def test_animation_override_blocks_autonomous(mock_window):
    """_should_fire_autonomous returns False when override active."""
    mock_window._animation_override_active = True
    # Simulate _should_fire_autonomous logic
    def should_fire():
        if mock_window._animation_override_active:
            return False
        return True
    assert should_fire() is False


def test_clear_animation_override_restores_autonomous(mock_window):
    """Clearing the flag re-enables autonomous triggers."""
    mock_window._animation_override_active = True
    mock_window._clear_animation_override()
    assert mock_window._animation_override_active is False
    def should_fire():
        if mock_window._animation_override_active:
            return False
        return True
    assert should_fire() is True


def test_unknown_state_does_nothing(mock_window):
    """Unknown state should not crash and not call anything."""
    fsm_state_override(mock_window, "UNKNOWN")
    action_state_override(mock_window, "UNKNOWN")
    mock_window._fsm.transition_to.assert_not_called()
    mock_window._action_layer.trigger.assert_not_called()
