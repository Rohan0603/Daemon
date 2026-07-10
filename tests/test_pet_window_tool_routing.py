"""Tests that LLM tool calls reach the correct animation path.

Two regressions are covered:
  * Expression actions like "jump" were routed to the FSM-only handler and
    silently dropped (pet_window._on_ollama_tool_call).
  * The MCP server's change_visual_state must route "jump" to the ActionLayer.
"""
from unittest.mock import MagicMock

from src.mcp_server import _handle_change_visual_state


def test_on_ollama_tool_call_routes_jump_to_expression(safe_pet_window):
    captured = []
    safe_pet_window._fsm_bridge.action_triggered.connect(
        lambda n, d, p: captured.append((n, d, p)))
    safe_pet_window._on_ollama_tool_call("change_visual_state", {"action": "jump"})
    assert captured, "expression action must reach the action_triggered signal"
    assert captured[0][0] == "jump"


def test_on_ollama_tool_call_routes_fsm_to_request(safe_pet_window):
    captured = []
    safe_pet_window._fsm_bridge.request.connect(lambda a, x, y: captured.append(a))
    safe_pet_window._on_ollama_tool_call("change_visual_state", {"action": "celebrate"})
    assert captured and captured[0] == "celebrate"


def test_server_change_visual_state_jump_routes_to_action_layer():
    thread = MagicMock()
    thread._fsm_bridge = MagicMock()
    thread._action_layer = MagicMock()
    thread._config = {"allow_intrusive_animations": True}
    _handle_change_visual_state(thread, "jump", "expression", 2000, 0, 0)
    thread._action_layer.trigger.assert_called_once_with("jump", 2000, {})
    thread._fsm_bridge.fsm_action_requested.emit.assert_not_called()
