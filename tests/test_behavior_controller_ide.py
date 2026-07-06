"""Tests for IDE coding assistant mode — behavior controller, events, and schema."""

import pytest
from unittest.mock import MagicMock, patch

from src.events import EventType


def test_ide_event_types_exist():
    assert hasattr(EventType, "IDE_MODE_ENTERED")
    assert hasattr(EventType, "IDE_MODE_EXITED")
    assert EventType.IDE_MODE_ENTERED.value == "ide_mode_entered"
    assert EventType.IDE_MODE_EXITED.value == "ide_mode_exited"


def test_code_assist_in_schema():
    from src.constants import STRUCTURED_SCHEMA
    enum_vals = STRUCTURED_SCHEMA["items"]["properties"]["type"]["enum"]
    assert "code_assist" in enum_vals


def _make_controller():
    from src.autonomy.behavior_controller import BehaviorController
    from src.pet_fsm import PetFSM, PetState

    event_bus = MagicMock()
    response_manager = MagicMock()
    typing_buffer = MagicMock()
    fsm = MagicMock(spec=PetFSM)
    fsm.current_state = PetState.IDLE
    animator = MagicMock()

    bc = BehaviorController(
        event_bus=event_bus,
        response_manager=response_manager,
        typing_buffer=typing_buffer,
        fsm=fsm,
        animator=animator,
        opencode_enabled=False,
    )
    return bc, event_bus


def test_in_ide_mode_starts_false():
    bc, _ = _make_controller()
    assert bc._in_ide_mode is False


def test_ide_mode_entered_event_published():
    bc, event_bus = _make_controller()
    bc._in_ide_mode = False
    with patch("src.autonomy.behavior_controller.get_active_window_title",
               return_value="main.py - Visual Studio Code"), \
         patch("src.autonomy.behavior_controller.is_ide_window", return_value=True):
        bc._check_ide_mode_transition()
    assert bc._in_ide_mode is True
    event_types = [c.args[0].type for c in event_bus.publish.call_args_list]
    assert EventType.IDE_MODE_ENTERED in event_types


def test_ide_mode_exited_event_published():
    bc, event_bus = _make_controller()
    bc._in_ide_mode = True
    with patch("src.autonomy.behavior_controller.get_active_window_title",
               return_value="Discord"), \
         patch("src.autonomy.behavior_controller.is_ide_window", return_value=False):
        bc._check_ide_mode_transition()
    assert bc._in_ide_mode is False
    event_types = [c.args[0].type for c in event_bus.publish.call_args_list]
    assert EventType.IDE_MODE_EXITED in event_types


def test_no_event_when_ide_mode_unchanged():
    bc, event_bus = _make_controller()
    bc._in_ide_mode = True
    with patch("src.autonomy.behavior_controller.get_active_window_title",
               return_value="main.py - Visual Studio Code"), \
         patch("src.autonomy.behavior_controller.is_ide_window", return_value=True):
        bc._check_ide_mode_transition()
    published_types = [c.args[0].type for c in event_bus.publish.call_args_list]
    assert EventType.IDE_MODE_ENTERED not in published_types
    assert EventType.IDE_MODE_EXITED not in published_types


def test_trigger_chat_draw_type_code_assist_in_ide():
    from src.events import EventBus
    from src.animator import Emotion

    bc, event_bus = _make_controller()
    bc._in_ide_mode = True
    bc._autonomous_query_pending = False
    bc._brain_disconnected = False
    bc._gcd_expiry_timestamp = 0.0
    bc._opencode_enabled = True
    bc._response_manager.thought_pool.remaining.return_value = 10

    # Mock get_active_window_title so we don't hit a real window
    with patch("src.autonomy.behavior_controller.get_active_window_title",
               return_value="main.py - Visual Studio Code"), \
         patch("src.autonomy.behavior_controller.is_ide_window", return_value=True), \
         patch("src.active_window.normalize_window_title", return_value="vscode"):
        bc._trigger_chat()

    assert event_bus.emit_autonomous_trigger.called
    call_kwargs = event_bus.emit_autonomous_trigger.call_args.kwargs
    assert call_kwargs["draw_type"] == "code_assist"


def test_trigger_chat_draw_type_typing_reaction_normally():
    from src.events import EventBus
    from src.animator import Emotion

    bc, event_bus = _make_controller()
    bc._in_ide_mode = False
    bc._autonomous_query_pending = False
    bc._brain_disconnected = False
    bc._gcd_expiry_timestamp = 0.0
    bc._opencode_enabled = True
    bc._response_manager.thought_pool.remaining.return_value = 10

    with patch("src.autonomy.behavior_controller.get_active_window_title",
               return_value="Discord"), \
         patch("src.autonomy.behavior_controller.is_ide_window", return_value=False):
        bc._trigger_chat()

    assert event_bus.emit_autonomous_trigger.called
    call_kwargs = event_bus.emit_autonomous_trigger.call_args.kwargs
    draw_type = call_kwargs.get("draw_type", "typing_reaction")
    assert draw_type == "typing_reaction"
