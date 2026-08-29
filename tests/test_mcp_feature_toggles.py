from unittest.mock import Mock

from src.mcp_server import _is_tool_allowed


def test_disabled_feature_blocks_tool():
    server = Mock()
    server._config = {}
    server._features = {"desktop_interaction": False}

    allowed, message = _is_tool_allowed(server, "vision_capture_screen")

    assert allowed is False
    assert "desktop_interaction" in message


def test_missing_feature_defaults_enabled():
    server = Mock()
    server._config = {}
    server._features = {}

    assert _is_tool_allowed(server, "lsp_get_diagnostics") == (True, "")
