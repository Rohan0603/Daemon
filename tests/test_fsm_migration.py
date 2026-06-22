from src.pet_fsm import PetState, FSMContext


def test_shaking_not_in_pet_state():
    assert not hasattr(PetState, "SHAKING")


def test_bouncing_not_in_pet_state():
    assert not hasattr(PetState, "BOUNCING")


def test_spinning_not_in_pet_state():
    assert not hasattr(PetState, "SPINNING")


def test_look_away_not_in_pet_state():
    assert not hasattr(PetState, "LOOK_AWAY")


def test_triggered_action_not_in_fsm_context():
    import dataclasses
    field_names = {f.name for f in dataclasses.fields(FSMContext)}
    assert "triggered_action" not in field_names


def test_fsm_context_can_be_constructed_without_triggered_action():
    # Ensure FSMContext no longer requires triggered_action
    ctx = FSMContext(
        cursor_pos=(0, 0), pet_rect=(0, 0, 60, 80),
        apm=0, is_dragged=False, is_falling=False,
        query_pending=False, build_event=None,
        idle_seconds=0.0, wander_due=False,
        hyper_sustained_seconds=0.0, hyper_cooldown_seconds=0.0,
        state_elapsed_ms=0, autonomous_query_pending=False,
    )
    assert ctx is not None


def test_on_mcp_fsm_action_no_attribute_errors(qapp):
    from src.pet_window import PetWindow
    from unittest.mock import patch, MagicMock
    
    with patch("src.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.pet_window.APMWorker"):
        window = PetWindow(opencode_enabled=False)
        window._fsm.transition_to = MagicMock()
        window._on_mcp_fsm_action("idle", None, None)
        window._fsm.transition_to.assert_called_with(PetState.IDLE)
