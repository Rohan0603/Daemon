import json
import os
import pytest
from unittest.mock import MagicMock, patch
from src.mcp_server import MCPHandler, MCPServer


def _handler(bridge=None, memory=None, diary_store=None):
    handler = object.__new__(MCPHandler)
    handler.server = MagicMock()
    handler.server.fsm_bridge = bridge if bridge is not None else MagicMock()
    handler.server.action_layer = MagicMock()
    handler.server.memory = memory
    handler.server.diary_store = diary_store
    handler.server.consent = {
        "allow_intrusive_animations": True,
        "allow_audio_disruptions": True,
        "allow_browser_redirection": True,
        "allow_clipboard_hijacking": True,
        "allow_mouse_interference": True,
        "allow_window_management": True,
        "allow_keyboard_injection": True,
    }
    handler._fsm_bridge = handler.server.fsm_bridge
    handler._action_layer = handler.server.action_layer
    handler._memory = memory
    handler._diary = diary_store
    handler._history = None
    handler._config = {"consent": handler.server.consent}
    return handler


from src.constants import THOUGHTS_LOG_PATH
from pathlib import Path
import io
import json


def test_post_log_writes_to_thoughts_and_logger():
    handler = _handler()
    payload = {
        "service": "opencode",
        "level": "ERROR",
        "message": "Connection reset",
        "extra": {"retries": 3},
    }
    body = json.dumps(payload).encode("utf-8")
    handler.client_address = ("127.0.0.1", 12345)
    handler.send_response = MagicMock()
    handler.end_headers = MagicMock()
    handler.log_request = MagicMock()
    handler.path = "/log"
    handler.requestline = "POST /log HTTP/1.1"
    handler.request_version = "HTTP/1.1"
    handler.command = "POST"
    handler.headers = {"Content-Length": str(len(body))}
    handler.rfile = io.BytesIO(body)
    handler.wfile = io.BytesIO()
    handler.do_POST()
    handler.wfile.seek(0)
    resp = json.loads(handler.wfile.read().decode("utf-8"))
    assert resp.get("success") is True
    content = Path(THOUGHTS_LOG_PATH).read_text(encoding="utf-8")
    assert "[opencode] Connection reset" in content


def test_post_session_summarize():
    handler = _handler()
    handler.server.fsm_bridge.emit_summarize_requested = MagicMock()
    payload = {
        "providerID": "openai",
        "modelID": "gpt-4",
    }
    body = json.dumps(payload).encode("utf-8")
    handler.client_address = ("127.0.0.1", 12345)
    handler.send_response = MagicMock()
    handler.end_headers = MagicMock()
    handler.log_request = MagicMock()
    handler.path = "/session/1234/summarize"
    handler.requestline = "POST /session/1234/summarize HTTP/1.1"
    handler.request_version = "HTTP/1.1"
    handler.command = "POST"
    handler.headers = {"Content-Length": str(len(body))}
    handler.rfile = io.BytesIO(body)
    handler.wfile = io.BytesIO()
    handler.do_POST()
    handler.wfile.seek(0)
    resp = json.loads(handler.wfile.read().decode("utf-8"))
    assert resp.get("success") is True
    assert "events" in resp
    handler.server.fsm_bridge.emit_summarize_requested.assert_called_once_with("openai", "gpt-4")


from src.mcp_server import _read_clipboard, _capture_blackmail_evidence


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


@patch("src.mcp_server._capture_blackmail_evidence",
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


def test_capture_blackmail_evidence_function_importable():
    """Verify _capture_blackmail_evidence is importable and callable."""
    assert callable(_capture_blackmail_evidence)


def test_tools_list_count():
    handler = _handler()
    response = handler._handle_tools_list()
    tools = response["result"]["tools"]
    assert len(tools) == 18
    names = [t["name"] for t in tools]
    assert "change_visual_state" in names
    assert "read_clipboard" in names
    assert "capture_blackmail_evidence" in names
    assert "send_system_toast" in names
    assert "list_directory" in names
    assert "read_file" in names
    assert "search_codebase" in names
    assert "get_memory" in names
    assert "get_diary" in names
    assert "simulate_keystroke" in names
    assert "move_mouse" in names
    assert "browser_navigation" in names


def test_tools_list():
    handler = _handler()
    response = handler._handle_tools_list()
    assert response["jsonrpc"] == "2.0"
    assert "result" in response
    assert len(response["result"]["tools"]) == 18
    tool = response["result"]["tools"][0]
    assert tool["name"] == "change_visual_state"
    assert "inputSchema" in tool


def test_tools_call_valid_action():
    handler = _handler()
    response = handler._handle_tools_call({
        "name": "change_visual_state",
        "arguments": {"action": "shake", "layer": "expression"}
    })
    assert response["jsonrpc"] == "2.0"
    assert response["result"]["content"][0]["text"] == "ok"
    handler.server.action_layer.trigger.assert_called_once_with("shake", None, {})


def test_tools_call_with_coords():
    handler = _handler()
    response = handler._handle_tools_call({
        "name": "change_visual_state",
        "arguments": {"action": "chase", "layer": "fsm", "target_x": 500, "target_y": 300}
    })
    assert response["result"]["content"][0]["text"] == "ok"
    handler.server.fsm_bridge.fsm_action_requested.emit.assert_called_once_with("chase")


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
        "arguments": {"action": "idle", "layer": "fsm"}
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
    server = MCPServer(MagicMock(), port=0)
    yield server
    server.stop()


def test_server_start_stop(mcp_server):
    mcp_server.start()
    assert mcp_server._server is not None
    mcp_server.stop()
    assert mcp_server._server is None


def test_mcp_validate_path_inside_root():
    from src.mcp_server import _validate_mcp_path
    PROJECT_ROOT = os.path.normpath(os.path.abspath("C:/Users/ponna/Project/Daemon"))

    result = _validate_mcp_path("src/pet_window.py", PROJECT_ROOT)
    expected = os.path.normpath(os.path.join(PROJECT_ROOT, "src/pet_window.py"))
    assert result == expected

    result = _validate_mcp_path("tests/test_fsm.py", PROJECT_ROOT)
    expected = os.path.normpath(os.path.join(PROJECT_ROOT, "tests/test_fsm.py"))
    assert result == expected

    result = _validate_mcp_path("README.md", PROJECT_ROOT)
    expected = os.path.normpath(os.path.join(PROJECT_ROOT, "README.md"))
    assert result == expected

    assert _validate_mcp_path("", PROJECT_ROOT) == PROJECT_ROOT


def test_mcp_validate_path_blocks_traversal():
    from src.mcp_server import _validate_mcp_path
    PROJECT_ROOT = os.path.normpath(os.path.abspath("C:/Users/ponna/Project/Daemon"))

    with pytest.raises(ValueError, match="Path traversal blocked"):
        _validate_mcp_path("../../etc/passwd", PROJECT_ROOT)
    with pytest.raises(ValueError, match="Path traversal blocked"):
        _validate_mcp_path("data/../../daemon.py", PROJECT_ROOT)
    with pytest.raises(ValueError, match="Path traversal blocked"):
        _validate_mcp_path("..\\..\\windows\\system32", PROJECT_ROOT)


def test_mcp_validate_path_blocks_outside_root():
    from src.mcp_server import _validate_mcp_path
    PROJECT_ROOT = os.path.normpath(os.path.abspath("C:/Users/ponna/Project/Daemon"))

    with pytest.raises(ValueError, match="Path traversal blocked"):
        _validate_mcp_path("C:/Windows/System32", PROJECT_ROOT)
    with pytest.raises(ValueError, match="Path traversal blocked"):
        _validate_mcp_path("/etc/passwd", PROJECT_ROOT)


def test_validate_read_extension():
    from src.mcp_server import _validate_read_extension

    assert _validate_read_extension("src/pet_window.py") is True
    assert _validate_read_extension("src/mcp_server.py") is True
    assert _validate_read_extension("README.md") is True
    assert _validate_read_extension("data/.daemon_memory.json") is True


    assert _validate_read_extension("src/__pycache__/something.cpython.pyc") is False
    assert _validate_read_extension("data/screenshot.png") is False
    assert _validate_read_extension("data/blackmail/evidence.png") is False
    assert _validate_read_extension("daemon.spec") is False


def test_tools_call_get_memory():
    mem = MagicMock()
    mem.get_all.return_value = {"name": "Alice", "profession": "developer"}
    handler = _handler(memory=mem)
    response = handler._handle_tools_call({"name": "get_memory", "arguments": {}})
    text = response["result"]["content"][0]["text"]
    assert "name: Alice" in text
    assert "profession: developer" in text
    assert "Memory facts" in text


def test_tools_call_get_memory_empty():
    mem = MagicMock()
    mem.get_all.return_value = {}
    handler = _handler(memory=mem)
    response = handler._handle_tools_call({"name": "get_memory", "arguments": {}})
    assert "No memory facts stored" in response["result"]["content"][0]["text"]


def test_tools_call_get_memory_no_memory():
    handler = _handler(memory=None)
    response = handler._handle_tools_call({"name": "get_memory", "arguments": {}})
    assert "Memory not available" in response["result"]["content"][0]["text"]


def test_tools_call_get_diary():
    store = MagicMock()
    store.get_entries.return_value = [
        {"content": "User learned Python", "timestamp": 1000},
        {"content": "User built a pet", "timestamp": 2000},
    ]
    handler = _handler(diary_store=store)
    response = handler._handle_tools_call({"name": "get_diary", "arguments": {}})
    text = response["result"]["content"][0]["text"]
    assert "User learned Python" in text
    assert "User built a pet" in text
    assert "Recent diary entries" in text


def test_tools_call_get_diary_empty():
    store = MagicMock()
    store.get_entries.return_value = []
    handler = _handler(diary_store=store)
    response = handler._handle_tools_call({"name": "get_diary", "arguments": {}})
    assert "No diary entries" in response["result"]["content"][0]["text"]


def test_tools_call_get_diary_with_limit():
    store = MagicMock()
    store.get_entries.return_value = [
        {"content": f"Entry {i}", "timestamp": i} for i in range(20)
    ]
    handler = _handler(diary_store=store)
    response = handler._handle_tools_call({"name": "get_diary", "arguments": {"limit": 3}})
    text = response["result"]["content"][0]["text"]
    assert "Entry 17" in text
    assert "Entry 18" in text
    assert "Entry 19" in text
    assert "Entry 0" not in text


def test_tools_call_get_diary_no_diary_store():
    handler = _handler(diary_store=None)
    response = handler._handle_tools_call({"name": "get_diary", "arguments": {}})
    assert "Diary not available" in response["result"]["content"][0]["text"]


def test_tools_call_get_diary_with_null_limit():
    store = MagicMock()
    store.get_entries.return_value = [
        {"content": f"Entry {i}", "timestamp": i} for i in range(5)
    ]
    handler = _handler(diary_store=store)
    response = handler._handle_tools_call({"name": "get_diary", "arguments": {"limit": None}})
    text = response["result"]["content"][0]["text"]
    assert "Entry 0" in text


def test_tools_list_includes_new_tools():
    handler = _handler()
    response = handler._handle_tools_list()
    names = [t["name"] for t in response["result"]["tools"]]
    assert "list_directory" in names
    assert "read_file" in names
    assert "search_codebase" in names
    assert "get_memory" in names
    assert "get_diary" in names
    assert "simulate_keystroke" in names
    assert "move_mouse" in names
    assert "browser_navigation" in names


def test_tools_call_list_directory_src():
    handler = _handler()
    response = handler._handle_tools_call({
        "name": "list_directory",
        "arguments": {"relative_path": "src"}
    })
    assert response["jsonrpc"] == "2.0"
    assert "result" in response
    content = json.loads(response["result"]["content"][0]["text"])
    names = [c["name"] for c in content]
    assert "pet_window.py" in names
    assert "mcp_server.py" in names


def test_tools_call_list_directory_nested():
    handler = _handler()
    response = handler._handle_tools_call({
        "name": "list_directory",
        "arguments": {"relative_path": "src"}  # valid
    })
    assert "result" in response


def test_tools_call_list_directory_file():
    handler = _handler()
    response = handler._handle_tools_call({
        "name": "list_directory",
        "arguments": {"relative_path": "src/pet_window.py"}  # file, not dir
    })
    assert "error" in response


def test_tools_call_list_directory_traversal_blocked():
    handler = _handler()
    response = handler._handle_tools_call({
        "name": "list_directory",
        "arguments": {"relative_path": "../../Windows"}
    })
    assert "error" in response


def test_tools_call_read_file_valid():
    handler = _handler()
    response = handler._handle_tools_call({
        "name": "read_file",
        "arguments": {"file_path": "src/constants.py"}
    })
    assert response["jsonrpc"] == "2.0"
    assert "result" in response
    text = response["result"]["content"][0]["text"]
    assert "STRUCTURED_SCHEMA" in text


def test_tools_call_read_file_pagination():
    handler = _handler()
    response = handler._handle_tools_call({
        "name": "read_file",
        "arguments": {"file_path": "src/constants.py", "start_line": 1, "end_line": 10}
    })
    text = response["result"]["content"][0]["text"]
    assert "lines 1-10" in text


def test_tools_call_read_file_blocked_path():
    handler = _handler()
    response = handler._handle_tools_call({
        "name": "read_file",
        "arguments": {"file_path": "../../etc/passwd"}
    })
    assert "error" in response


def test_tools_call_search_codebase():
    handler = _handler()
    response = handler._handle_tools_call({
        "name": "search_codebase",
        "arguments": {"search_term": "class PetWindow"}
    })
    assert response["jsonrpc"] == "2.0"
    text = response["result"]["content"][0]["text"]
    results = json.loads(text)
    assert len(results) >= 1
    assert any("pet_window.py" in r["file"] for r in results)


# ── Consent gating tests (Phase 44.5 Gap 1) ────────────────────────────────

def _consent_handler(overrides: dict[str, bool] | None = None, bridge=None):
    """Build a handler with a consent dict. All gates default False."""
    consent = {
        "allow_intrusive_animations": False,
        "allow_audio_disruptions": False,
        "allow_clipboard_hijacking": False,
        "allow_window_management": False,
        "allow_keyboard_injection": False,
        "allow_mouse_interference": False,
        "allow_browser_redirection": False,
    }
    if overrides:
        consent.update(overrides)
    handler = object.__new__(MCPHandler)
    handler.server = MagicMock()
    handler.server.fsm_bridge = bridge if bridge is not None else MagicMock()
    handler.server.action_layer = MagicMock()
    handler.server.memory = None
    handler.server.diary_store = None
    handler.server.consent = consent
    handler._fsm_bridge = handler.server.fsm_bridge
    handler._action_layer = handler.server.action_layer
    handler._memory = None
    handler._diary = None
    handler._history = None
    handler._config = {"consent": consent}
    return handler


def test_consent_block_change_visual_state():
    handler = _consent_handler()
    response = handler._handle_tools_call({
        "name": "change_visual_state",
        "arguments": {"action": "shake", "layer": "expression"}
    })
    assert "error" in response
    assert response["error"]["code"] == -32001
    assert "denied permission" in response["error"]["message"]
    assert "allow_intrusive_animations" in response["error"]["message"]


def test_consent_allow_change_visual_state():
    handler = _consent_handler({"allow_intrusive_animations": True})
    response = handler._handle_tools_call({
        "name": "change_visual_state",
        "arguments": {"action": "shake", "layer": "expression"}
    })
    assert "result" in response
    handler.server.action_layer.trigger.assert_called_once_with("shake", None, {})


def test_consent_block_read_clipboard():
    handler = _consent_handler()
    response = handler._handle_tools_call({
        "name": "read_clipboard",
        "arguments": {}
    })
    assert "error" in response
    assert response["error"]["code"] == -32001
    assert "allow_clipboard_hijacking" in response["error"]["message"]


@patch("src.mcp_server._read_clipboard", return_value="Clipboard: test")
def test_consent_allow_read_clipboard(mock_read):
    handler = _consent_handler({"allow_clipboard_hijacking": True})
    response = handler._handle_tools_call({
        "name": "read_clipboard",
        "arguments": {}
    })
    assert "result" in response
    assert "Clipboard: test" in response["result"]["content"][0]["text"]


def test_consent_block_capture_blackmail_evidence():
    handler = _consent_handler()
    response = handler._handle_tools_call({
        "name": "capture_blackmail_evidence",
        "arguments": {}
    })
    assert "error" in response
    assert "allow_window_management" in response["error"]["message"]


def test_consent_block_send_system_toast():
    handler = _consent_handler()
    response = handler._handle_tools_call({
        "name": "send_system_toast",
        "arguments": {}
    })
    assert "error" in response
    assert "allow_audio_disruptions" in response["error"]["message"]


def test_consent_read_only_tools_not_blocked():
    """Read-only tools (list_directory, read_file, etc) should pass without consent."""
    handler = _consent_handler()
    # These tools don't need consent — pass minimal valid args
    for name, args in (
        ("list_directory", {"relative_path": "src"}),
        ("get_memory", {}),
        ("get_diary", {}),
    ):
        response = handler._handle_tools_call({"name": name, "arguments": args})
        assert "error" not in response, f"Tool '{name}' blocked by consent"


def test_consent_parse_raw_blocks_gated_tool():
    consent = {k: False for k in ("allow_intrusive_animations", "allow_audio_disruptions",
                                   "allow_clipboard_hijacking", "allow_window_management",
                                   "allow_keyboard_injection", "allow_mouse_interference",
                                   "allow_browser_redirection")}
    body = json.dumps({
        "method": "tools/call",
        "params": {"name": "change_visual_state", "arguments": {"action": "shake", "layer": "expression"}},
        "id": 1,
    })
    response = MCPHandler.parse_raw(body, consent)
    assert "error" in response
    assert response["error"]["code"] == -32001


def test_consent_parse_raw_allows_with_permission():
    consent = {k: True for k in ("allow_intrusive_animations", "allow_audio_disruptions",
                                  "allow_clipboard_hijacking", "allow_window_management",
                                  "allow_keyboard_injection", "allow_mouse_interference",
                                  "allow_browser_redirection")}
    body = json.dumps({
        "method": "tools/call",
        "params": {"name": "change_visual_state", "arguments": {"action": "shake", "layer": "expression"}},
        "id": 1,
    })
    response = MCPHandler.parse_raw(body, consent)
    assert "result" in response


# --- Phase 45: Puppeteer tool tests ---

@patch("src.mcp_server._simulate_keystroke", return_value="Typed 3 characters")
def test_tools_call_simulate_keystroke(mock_ks):
    handler = _consent_handler({"allow_keyboard_injection": True})
    response = handler._handle_tools_call({
        "name": "simulate_keystroke",
        "arguments": {"keys": "foo"}
    })
    assert response["result"]["content"][0]["text"] == "Typed 3 characters"


def test_consent_block_simulate_keystroke():
    handler = _consent_handler()
    response = handler._handle_tools_call({
        "name": "simulate_keystroke",
        "arguments": {"keys": "foo"}
    })
    assert "error" in response
    assert "allow_keyboard_injection" in response["error"]["message"]


def test_simulate_keystroke_window_key_blocked():
    from src.mcp_server import _simulate_keystroke
    result = _simulate_keystroke("win+r notepad")
    assert "Windows key is blocked" in result


@patch("src.mcp_server._move_mouse", return_value="Moved cursor to (100, 200)")
def test_tools_call_move_mouse(mock_mm):
    handler = _consent_handler({"allow_mouse_interference": True})
    response = handler._handle_tools_call({
        "name": "move_mouse",
        "arguments": {"x": 100, "y": 200}
    })
    assert "Moved cursor to (100, 200)" in response["result"]["content"][0]["text"]


def test_consent_block_move_mouse():
    handler = _consent_handler()
    response = handler._handle_tools_call({
        "name": "move_mouse",
        "arguments": {"x": 100, "y": 200}
    })
    assert "error" in response
    assert "allow_mouse_interference" in response["error"]["message"]


@patch("src.mcp_server._move_mouse", return_value="Moved cursor to (0, 0) and clicked")
def test_tools_call_move_mouse_with_click(mock_mm):
    handler = _consent_handler({"allow_mouse_interference": True})
    response = handler._handle_tools_call({
        "name": "move_mouse",
        "arguments": {"x": -5, "y": -5, "click": True}
    })
    assert "clicked" in response["result"]["content"][0]["text"]


@patch("src.mcp_server._browser_navigation", return_value="Opened https://example.com")
def test_tools_call_browser_navigation(mock_bn):
    handler = _consent_handler({"allow_browser_redirection": True})
    response = handler._handle_tools_call({
        "name": "browser_navigation",
        "arguments": {"url": "https://example.com"}
    })
    assert "Opened https://example.com" in response["result"]["content"][0]["text"]


def test_consent_block_browser_navigation():
    handler = _consent_handler()
    response = handler._handle_tools_call({
        "name": "browser_navigation",
        "arguments": {"url": "https://example.com"}
    })
    assert "error" in response
    assert "allow_browser_redirection" in response["error"]["message"]


def test_browser_navigation_blocked_scheme():
    from src.mcp_server import _browser_navigation
    result = _browser_navigation("javascript:alert(1)")
    assert "Only http:// and https://" in result
