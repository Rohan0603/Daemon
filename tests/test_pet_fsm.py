import pytest
from src.pet_fsm import PetFSM, PetState


def test_transition_to_changes_state():
    fsm = PetFSM()
    assert fsm.current_state == PetState.IDLE
    fsm.transition_to(PetState.SHAKING)
    assert fsm.current_state == PetState.SHAKING


def test_transition_to_logs_via_callback():
    fsm = PetFSM()
    captured = []
    fsm.transition_to(PetState.HYPER, on_transition=lambda old, new: captured.append((old, new)))
    assert len(captured) == 1
    assert captured[0] == (PetState.IDLE, PetState.HYPER)


def test_transition_to_same_state_is_noop():
    fsm = PetFSM()
    captured = []
    fsm.current_state = PetState.SLEEP
    fsm.transition_to(PetState.SLEEP, on_transition=lambda old, new: captured.append((old, new)))
    assert len(captured) == 0
    assert fsm.current_state == PetState.SLEEP
