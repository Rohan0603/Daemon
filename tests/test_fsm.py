import pytest
from dataclasses import dataclass
from src.pet_fsm import PetFSM, PetState, FSMContext
from src.constants import (
    SHAKE_DURATION_MS, BOUNCE_DURATION_MS,
    SPIN_DURATION_MS, LOOK_AWAY_DURATION_MS,
)


def make_context(**overrides) -> FSMContext:
    defaults = dict(
        cursor_pos=(9999, 9999),
        pet_rect=(100, 900, 40, 50),  # (x, y, w, h)
        apm=0,
        is_dragged=False,
        is_falling=False,
        query_pending=False,
        build_event=None,
        idle_seconds=0.0,
        wander_due=False,
        hyper_sustained_seconds=0.0,
        hyper_cooldown_seconds=0.0,
        state_elapsed_ms=0,
        autonomous_query_pending=False,
    )
    defaults.update(overrides)
    return FSMContext(**defaults)


def test_initial_state_is_idle():
    fsm = PetFSM()
    assert fsm.current_state == PetState.IDLE


def test_wander_due_triggers_wander_from_idle():
    fsm = PetFSM()
    ctx = make_context(wander_due=True)
    new_state = fsm.update(33, ctx)
    assert new_state == PetState.PERIMETER


def test_wander_not_triggered_if_higher_priority():
    fsm = PetFSM()
    fsm.current_state = PetState.IDLE
    ctx = make_context(wander_due=True, is_dragged=True)
    new_state = fsm.update(33, ctx)
    assert new_state == PetState.DRAGGED


def test_dragged_interrupts_wander():
    fsm = PetFSM()
    fsm.current_state = PetState.PERIMETER
    ctx = make_context(is_dragged=True)
    new_state = fsm.update(33, ctx)
    assert new_state == PetState.DRAGGED


def test_falling_after_drag_release_below_ground():
    fsm = PetFSM()
    fsm.current_state = PetState.DRAGGED
    ctx = make_context(is_dragged=False, is_falling=True)
    new_state = fsm.update(33, ctx)
    assert new_state == PetState.FALLING


def test_falling_exits_to_idle_when_grounded():
    fsm = PetFSM()
    fsm.current_state = PetState.FALLING
    ctx = make_context(is_falling=False)
    new_state = fsm.update(33, ctx)
    assert new_state == PetState.IDLE


def test_sleep_triggers_after_idle_seconds():
    from src.constants import SLEEP_IDLE_SECONDS
    fsm = PetFSM()
    ctx = make_context(idle_seconds=SLEEP_IDLE_SECONDS + 1)
    new_state = fsm.update(33, ctx)
    assert new_state == PetState.SLEEP


def test_any_event_wakes_from_sleep():
    fsm = PetFSM()
    fsm.current_state = PetState.SLEEP
    ctx = make_context(idle_seconds=0.0)
    new_state = fsm.update(33, ctx)
    assert new_state == PetState.IDLE


def test_chase_triggers_when_cursor_near():
    from src.constants import CHASE_ENTER_RADIUS_PX
    fsm = PetFSM()
    # pet center at (120, 925); cursor 50px away
    ctx = make_context(
        cursor_pos=(120, 875),
        pet_rect=(100, 900, 40, 50)
    )
    new_state = fsm.update(33, ctx)
    assert new_state == PetState.CHASE


def test_chase_exits_when_cursor_far():
    from src.constants import CHASE_EXIT_RADIUS_PX
    fsm = PetFSM()
    fsm.current_state = PetState.CHASE
    # cursor 300px away (> CHASE_EXIT_RADIUS_PX=250)
    ctx = make_context(
        cursor_pos=(120 + 300, 925),
        pet_rect=(100, 900, 40, 50)
    )
    new_state = fsm.update(33, ctx)
    assert new_state == PetState.IDLE


def test_hyper_triggers_after_sustained_apm():
    from src.constants import APM_HYPER_THRESHOLD
    fsm = PetFSM()
    ctx = make_context(apm=APM_HYPER_THRESHOLD + 10, hyper_sustained_seconds=4.0)
    new_state = fsm.update(33, ctx)
    assert new_state == PetState.HYPER


def test_hyper_exits_after_cooldown():
    fsm = PetFSM()
    fsm.current_state = PetState.HYPER
    ctx = make_context(apm=0, hyper_cooldown_seconds=11.0)
    new_state = fsm.update(33, ctx)
    assert new_state == PetState.IDLE


def test_thinking_overrides_chase():
    fsm = PetFSM()
    fsm.current_state = PetState.CHASE
    ctx = make_context(query_pending=True, cursor_pos=(120, 875), pet_rect=(100, 900, 40, 50))
    new_state = fsm.update(33, ctx)
    assert new_state == PetState.THINKING


def test_celebrate_runs_then_returns_to_idle():
    fsm = PetFSM()
    fsm.current_state = PetState.CELEBRATE
    ctx = make_context(state_elapsed_ms=3100)
    new_state = fsm.update(33, ctx)
    assert new_state == PetState.IDLE


def test_devastated_runs_then_returns_to_idle():
    fsm = PetFSM()
    fsm.current_state = PetState.DEVASTATED
    ctx = make_context(state_elapsed_ms=5100)
    new_state = fsm.update(33, ctx)
    assert new_state == PetState.IDLE


def test_celebrate_can_be_interrupted_by_dragged():
    fsm = PetFSM()
    fsm.current_state = PetState.CELEBRATE
    ctx = make_context(is_dragged=True, state_elapsed_ms=500)
    new_state = fsm.update(33, ctx)
    assert new_state == PetState.DRAGGED


def test_build_success_triggers_celebrate():
    fsm = PetFSM()
    ctx = make_context(build_event="success")
    new_state = fsm.update(33, ctx)
    assert new_state == PetState.CELEBRATE


def test_build_failure_triggers_devastated():
    fsm = PetFSM()
    ctx = make_context(build_event="failure")
    new_state = fsm.update(33, ctx)
    assert new_state == PetState.DEVASTATED


def test_autonomous_thinking_when_flag_set():
    fsm = PetFSM()
    fsm.current_state = PetState.IDLE
    ctx = make_context(autonomous_query_pending=True)
    assert fsm.update(33, ctx) == PetState.AUTONOMOUS_THINKING


def test_autonomous_thinking_lower_priority_than_user_thinking():
    fsm = PetFSM()
    fsm.current_state = PetState.IDLE
    ctx = make_context(query_pending=True, autonomous_query_pending=True)
    assert fsm.update(33, ctx) == PetState.THINKING


def test_autonomous_thinking_overrides_wander():
    fsm = PetFSM()
    fsm.current_state = PetState.PERIMETER
    ctx = make_context(autonomous_query_pending=True)
    assert fsm.update(33, ctx) == PetState.AUTONOMOUS_THINKING


def test_autonomous_thinking_exits_when_flag_cleared():
    fsm = PetFSM()
    fsm.current_state = PetState.AUTONOMOUS_THINKING
    ctx = make_context(autonomous_query_pending=False)
    result = fsm.update(33, ctx)
    assert result == PetState.IDLE


def test_triggered_action_hyper_enters_hyper():
    fsm = PetFSM()
    ctx = make_context(triggered_action="hyper")
    assert fsm.update(33, ctx) == PetState.HYPER


def test_triggered_action_shake_enters_shaking():
    fsm = PetFSM()
    ctx = make_context(triggered_action="shake")
    assert fsm.update(33, ctx) == PetState.SHAKING


def test_triggered_action_bounce_enters_bouncing():
    fsm = PetFSM()
    ctx = make_context(triggered_action="bounce")
    assert fsm.update(33, ctx) == PetState.BOUNCING


def test_triggered_action_spin_enters_spinning():
    fsm = PetFSM()
    ctx = make_context(triggered_action="spin")
    assert fsm.update(33, ctx) == PetState.SPINNING


def test_triggered_action_look_away_enters_look_away():
    fsm = PetFSM()
    ctx = make_context(triggered_action="look_away")
    assert fsm.update(33, ctx) == PetState.LOOK_AWAY


def test_shaking_exits_after_duration():
    fsm = PetFSM()
    fsm.current_state = PetState.SHAKING
    ctx = make_context(state_elapsed_ms=SHAKE_DURATION_MS + 1)
    assert fsm.update(33, ctx) == PetState.IDLE


def test_bouncing_exits_after_duration():
    fsm = PetFSM()
    fsm.current_state = PetState.BOUNCING
    ctx = make_context(state_elapsed_ms=BOUNCE_DURATION_MS + 1)
    assert fsm.update(33, ctx) == PetState.IDLE


def test_spinning_exits_after_duration():
    fsm = PetFSM()
    fsm.current_state = PetState.SPINNING
    ctx = make_context(state_elapsed_ms=SPIN_DURATION_MS + 1)
    assert fsm.update(33, ctx) == PetState.IDLE


def test_look_away_exits_after_duration():
    fsm = PetFSM()
    fsm.current_state = PetState.LOOK_AWAY
    ctx = make_context(state_elapsed_ms=LOOK_AWAY_DURATION_MS + 1)
    assert fsm.update(33, ctx) == PetState.IDLE
