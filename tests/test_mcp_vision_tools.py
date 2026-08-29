import json
from unittest.mock import Mock, patch

from src.mcp_server import (
    CONSENT_TOOL_MAP,
    MCPServerThread,
    _create_fastmcp_app,
    _handle_vision_capture_screen,
    _handle_vision_click_coordinate,
    _is_tool_allowed,
)


def _thread(consent):
    thread = Mock(spec=MCPServerThread)
    thread._config = consent
    thread._fsm_bridge = Mock()
    thread._action_layer = Mock()
    thread._memory = thread._diary_store = thread._history = None
    return thread


def test_vision_capture_requires_window_management_consent():
    thread = _thread({"allow_window_management": False})

    result = _handle_vision_capture_screen(thread, None, True, False)

    assert "blocked" in result["content"][0]["text"]
    assert CONSENT_TOOL_MAP["vision_capture_screen"] == "allow_window_management"
    assert _is_tool_allowed(thread, "vision_capture_screen")[0] is False


def test_vision_capture_delegates_to_controller():
    controller = Mock()
    controller.capture_screen.return_value = {"image_base64": "abc", "grid_overlay": True}
    thread = _thread({"allow_window_management": True})
    with patch("src.system.vision_controller.VisionController", return_value=controller):
        result = _handle_vision_capture_screen(thread, [1, 2, 3, 4], True, False)

    assert json.loads(result["content"][0]["text"])["image_base64"] == "abc"
    controller.capture_screen.assert_called_once_with((1, 2, 3, 4), True, False)


def test_vision_click_requires_mouse_consent():
    thread = _thread({"allow_mouse_interference": False})

    result = _handle_vision_click_coordinate(thread, 1, 2, "left", False, 0)

    assert "blocked" in result["content"][0]["text"]
    assert CONSENT_TOOL_MAP["vision_click_coordinate"] == "allow_mouse_interference"


def test_vision_tools_are_registered():
    app = _create_fastmcp_app(_thread({"allow_window_management": True, "allow_mouse_interference": True}))

    assert "vision_capture_screen" in app._tool_manager._tools
    assert "vision_click_coordinate" in app._tool_manager._tools
