"""Test animation routing in FastMCP server.

Calls _handle_change_visual_state directly.
"""
from unittest.mock import MagicMock
from src.mcp_server import _handle_change_visual_state


def _make_thread(fsm_bridge=None, action_layer=None):
    thread = MagicMock()
    thread._fsm_bridge = fsm_bridge or MagicMock()
    thread._action_layer = action_layer or MagicMock()
    thread._config = {"allow_intrusive_animations": True}
    return thread


def test_expression_layer_routes_to_action_layer():
    thread = _make_thread()
    _handle_change_visual_state(thread, "float", "expression", 2000, 0, 0)
    thread._action_layer.trigger.assert_called_once()
    thread._fsm_bridge.fsm_action_requested.emit.assert_not_called()


def test_fsm_layer_routes_to_fsm_bridge():
    thread = _make_thread()
    _handle_change_visual_state(thread, "celebrate", "fsm", 2000, 0, 0)
    thread._fsm_bridge.fsm_action_requested.emit.assert_called_once_with("celebrate")
    thread._action_layer.trigger.assert_not_called()


def test_expression_action_on_fsm_layer_is_auto_corrected():
    """Expression action on fsm layer should auto-correct to expression, not error."""
    thread = _make_thread()
    result = _handle_change_visual_state(thread, "float", "fsm", 2000, 0, 0)
    text = result["content"][0]["text"]
    assert "Invalid" not in text and "error" not in text.lower()
    thread._action_layer.trigger.assert_called_once()
    thread._fsm_bridge.fsm_action_requested.emit.assert_not_called()


def test_fsm_action_on_expression_layer_is_auto_corrected():
    """FSM action on expression layer should auto-correct to fsm, not error."""
    thread = _make_thread()
    result = _handle_change_visual_state(thread, "celebrate", "expression", 2000, 0, 0)
    text = result["content"][0]["text"]
    assert "Invalid" not in text and "error" not in text.lower()
    thread._fsm_bridge.fsm_action_requested.emit.assert_called_once_with("celebrate")
    thread._action_layer.trigger.assert_not_called()


def test_duration_ms_passed_to_action_layer():
    thread = _make_thread()
    _handle_change_visual_state(thread, "rainbow", "expression", 3000, 0, 0)
    thread._action_layer.trigger.assert_called_once_with("rainbow", 3000, {})
