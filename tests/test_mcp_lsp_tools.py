import json
from unittest.mock import Mock, patch

from src.mcp_server import (
    MCPServerThread,
    _create_fastmcp_app,
    _handle_lsp_get_diagnostics,
    _handle_lsp_get_symbol_info,
)


def test_lsp_tools_return_explicit_unconfigured_error():
    thread = Mock(spec=MCPServerThread)
    thread._lsp_client = None

    result = _handle_lsp_get_diagnostics(thread, None)

    assert json.loads(result["content"][0]["text"])["error"] == "LSP is not configured"


def test_lsp_handlers_delegate_to_client():
    client = Mock()
    client.running = True
    client.get_diagnostics.return_value = [{"message": "bad"}]
    client.symbol_info.return_value = {"definitions": [], "references": []}
    thread = Mock(spec=MCPServerThread)
    thread._lsp_client = client

    with patch("src.mcp_server._get_lsp_client", return_value=client):
        diagnostics = _handle_lsp_get_diagnostics(thread, "main.py")
        symbols = _handle_lsp_get_symbol_info(thread, "main.py", 2, 3)

    assert json.loads(diagnostics["content"][0]["text"]) == [{"message": "bad"}]
    assert json.loads(symbols["content"][0]["text"]) == {"definitions": [], "references": []}


def test_lsp_tools_are_registered():
    thread = Mock(spec=MCPServerThread)
    thread._config = {}
    thread._fsm_bridge = Mock()
    thread._action_layer = Mock()
    thread._memory = thread._diary_store = thread._history = None

    app = _create_fastmcp_app(thread)

    assert "lsp_get_diagnostics" in app._tool_manager._tools
    assert "lsp_get_symbol_info" in app._tool_manager._tools
