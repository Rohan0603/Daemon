import json
from unittest.mock import Mock, patch

from src.mcp_server import (
    CONSENT_TOOL_MAP,
    MCPServerThread,
    _create_fastmcp_app,
    _handle_uia_get_window_tree,
    _handle_uia_interact_element,
    _is_tool_allowed,
)


def _thread(consent):
    thread = Mock(spec=MCPServerThread)
    thread._config = consent
    return thread


def test_uia_tree_tool_is_always_allowed_and_returns_json():
    navigator = Mock()
    navigator.dump_tree.return_value = {
        "window_handle": 42,
        "window_title": "Notepad",
        "tree": [],
        "truncated": False,
        "error": None,
    }
    with patch("src.system.uia_navigator.UIANavigator", return_value=navigator):
        result = _handle_uia_get_window_tree(_thread({}), 42, 2)

    assert "uia_get_window_tree" not in CONSENT_TOOL_MAP
    assert json.loads(result["content"][0]["text"])["window_handle"] == 42
    navigator.dump_tree.assert_called_once_with(42, 2)


def test_uia_tools_are_registered_with_fastmcp():
    thread = _thread({"allow_window_management": True})
    thread._fsm_bridge = Mock()
    thread._action_layer = Mock()
    thread._memory = None
    thread._diary_store = None
    thread._history = None

    app = _create_fastmcp_app(thread)

    assert "uia_get_window_tree" in app._tool_manager._tools
    assert "uia_interact_element" in app._tool_manager._tools


def test_uia_interaction_is_blocked_without_window_management_consent():
    thread = _thread({"allow_window_management": False})

    result = _handle_uia_interact_element(
        thread, {"name": "Save"}, "click", None, 42
    )

    assert CONSENT_TOOL_MAP["uia_interact_element"] == "allow_window_management"
    assert _is_tool_allowed(thread, "uia_interact_element")[0] is False
    assert "blocked" in result["content"][0]["text"]


def test_uia_interaction_delegates_when_allowed():
    navigator = Mock()
    navigator.invoke_element.return_value = {
        "success": True,
        "result": "click completed",
        "error": None,
    }
    thread = _thread({"allow_window_management": True})
    with patch("src.system.uia_navigator.UIANavigator", return_value=navigator):
        result = _handle_uia_interact_element(
            thread, {"automation_id": "saveButton"}, "click", None, 42
        )

    assert json.loads(result["content"][0]["text"])["success"] is True
    navigator.invoke_element.assert_called_once_with(
        42, {"automation_id": "saveButton"}, "click", None
    )
