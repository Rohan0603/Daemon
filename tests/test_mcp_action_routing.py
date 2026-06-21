import json
import pytest
from unittest.mock import MagicMock, patch


def _make_handler(fsm_bridge=None, action_layer=None):
    from src.mcp_server import MCPHandler
    handler = MCPHandler.__new__(MCPHandler)
    handler._fsm_bridge = fsm_bridge or MagicMock()
    handler._action_layer = action_layer or MagicMock()
    handler._config = {"consent": {}}
    return handler


def test_expression_layer_routes_to_action_layer():
    handler = _make_handler()
    params = {"action": "float", "layer": "expression"}
    handler._handle_change_visual_state(params)
    handler._action_layer.trigger.assert_called_once()
    handler._fsm_bridge.fsm_action_requested.emit.assert_not_called()


def test_fsm_layer_routes_to_fsm_bridge():
    handler = _make_handler()
    params = {"action": "celebrate", "layer": "fsm"}
    handler._handle_change_visual_state(params)
    handler._fsm_bridge.fsm_action_requested.emit.assert_called_once_with("celebrate")
    handler._action_layer.trigger.assert_not_called()


def test_expression_action_on_fsm_layer_returns_error():
    handler = _make_handler()
    params = {"action": "float", "layer": "fsm"}
    result = handler._handle_change_visual_state(params)
    assert result.get("error") is not None


def test_fsm_action_on_expression_layer_returns_error():
    handler = _make_handler()
    params = {"action": "celebrate", "layer": "expression"}
    result = handler._handle_change_visual_state(params)
    assert result.get("error") is not None


def test_duration_ms_passed_to_action_layer():
    handler = _make_handler()
    params = {"action": "rainbow", "layer": "expression", "duration_ms": 3000}
    handler._handle_change_visual_state(params)
    handler._action_layer.trigger.assert_called_once_with("rainbow", 3000, {})
