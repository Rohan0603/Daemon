import pytest
from unittest.mock import MagicMock
from src.mcp_server import MCPHandler, MCPServer


def _handler(bridge=None):
    handler = object.__new__(MCPHandler)
    handler.fsm_bridge = bridge if bridge is not None else MagicMock()
    return handler


def test_tools_list():
    handler = _handler()
    response = handler._handle_tools_list()
    assert response["jsonrpc"] == "2.0"
    assert "result" in response
    assert len(response["result"]["tools"]) == 1
    tool = response["result"]["tools"][0]
    assert tool["name"] == "change_visual_state"
    assert "inputSchema" in tool


def test_tools_call_valid_action():
    handler = _handler()
    response = handler._handle_tools_call({
        "name": "change_visual_state",
        "arguments": {"action": "shake"}
    })
    assert response["jsonrpc"] == "2.0"
    assert response["result"]["content"][0]["text"] == "ok"
    handler.fsm_bridge.emit_request.assert_called_once_with("shake", None, None)


def test_tools_call_with_coords():
    handler = _handler()
    response = handler._handle_tools_call({
        "name": "change_visual_state",
        "arguments": {"action": "chase", "target_x": 500, "target_y": 300}
    })
    assert response["result"]["content"][0]["text"] == "ok"
    handler.fsm_bridge.emit_request.assert_called_once_with("chase", 500, 300)


def test_tools_call_invalid_action():
    handler = _handler()
    response = handler._handle_tools_call({
        "name": "change_visual_state",
        "arguments": {"action": "fly"}
    })
    assert "error" in response
    assert response["error"]["code"] == -32602


def test_tools_call_missing_action():
    handler = _handler()
    response = handler._handle_tools_call({
        "name": "change_visual_state",
        "arguments": {}
    })
    assert "error" in response


def test_unknown_method():
    handler = _handler()
    response = handler._handle_request("unknown_method", {})
    assert "error" in response
    assert response["error"]["code"] == -32601


def test_parse_error_on_bad_json():
    response = MCPHandler.parse_raw("not json")
    assert "error" in response
    assert response["error"]["code"] == -32700


def test_tools_call_fsm_transition_with_no_bridge():
    handler = _handler(bridge=None)
    response = handler._handle_tools_call({
        "name": "change_visual_state",
        "arguments": {"action": "idle"}
    })
    assert response["result"]["content"][0]["text"] == "ok"


@pytest.fixture
def mcp_server():
    server = MCPServer(MagicMock())
    yield server
    server.stop()


def test_server_start_stop(mcp_server):
    mcp_server.start()
    assert mcp_server._server is not None
    mcp_server.stop()
    assert mcp_server._server is None
