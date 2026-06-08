import pytest
from unittest.mock import MagicMock, patch
from src.mcp_server import MCPHandler, MCPServer


def _handler(bridge=None):
    handler = object.__new__(MCPHandler)
    handler.fsm_bridge = bridge if bridge is not None else MagicMock()
    return handler


from src.mcp_server import _read_clipboard, _capture_screenshot


@patch("src.mcp_server._read_clipboard", return_value="Clipboard: def foo():\n    pass")
def test_tools_call_read_clipboard(mock_read):
    handler = _handler()
    response = handler._handle_tools_call({
        "name": "read_clipboard",
        "arguments": {}
    })
    assert response["result"]["content"][0]["text"] == "Clipboard: def foo():\n    pass"
    mock_read.assert_called_once_with()


@patch("src.mcp_server._read_clipboard", return_value="Clipboard: (empty or non-text data)")
def test_tools_call_read_clipboard_empty(mock_read):
    handler = _handler()
    response = handler._handle_tools_call({
        "name": "read_clipboard",
        "arguments": {}
    })
    assert "(empty or non-text data)" in response["result"]["content"][0]["text"]


def test_read_clipboard_function_importable():
    """Verify _read_clipboard is importable and callable."""
    assert callable(_read_clipboard)


@patch("src.mcp_server._capture_screenshot",
       return_value="Evidence saved to data/blackmail/evidence_2026-06-09_12-00-00.png")
def test_tools_call_capture_blackmail_evidence(mock_cap):
    handler = _handler()
    response = handler._handle_tools_call({
        "name": "capture_blackmail_evidence",
        "arguments": {}
    })
    text = response["result"]["content"][0]["text"]
    assert text.startswith("Evidence saved to data/blackmail/")
    mock_cap.assert_called_once_with()


def test_capture_screenshot_function_importable():
    """Verify _capture_screenshot is importable and callable."""
    assert callable(_capture_screenshot)


def test_tools_list_count():
    handler = _handler()
    response = handler._handle_tools_list()
    tools = response["result"]["tools"]
    assert len(tools) == 4
    names = [t["name"] for t in tools]
    assert "change_visual_state" in names
    assert "read_clipboard" in names
    assert "capture_blackmail_evidence" in names
    assert "send_system_toast" in names


def test_tools_list():
    handler = _handler()
    response = handler._handle_tools_list()
    assert response["jsonrpc"] == "2.0"
    assert "result" in response
    assert len(response["result"]["tools"]) == 4
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


def test_tools_call_send_system_toast():
    bridge = MagicMock()
    handler = _handler(bridge=bridge)
    response = handler._handle_tools_call({
        "name": "send_system_toast",
        "arguments": {"title": "Ammi Alert", "message": "He's gaming again"}
    })
    assert response["result"]["content"][0]["text"] == "toast sent"
    bridge.emit_toast.assert_called_once_with("Ammi Alert", "He's gaming again")


def test_tools_call_send_system_toast_defaults():
    bridge = MagicMock()
    handler = _handler(bridge=bridge)
    response = handler._handle_tools_call({
        "name": "send_system_toast",
        "arguments": {}
    })
    assert response["result"]["content"][0]["text"] == "toast sent"
    bridge.emit_toast.assert_called_once_with("Alert", "")


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
