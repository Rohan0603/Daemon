"""MCP server tests migrated to FastMCP.

See tests/test_mcp_server_fastmcp.py for the current test suite.
The old http.server-based MCPHandler has been replaced with FastMCP SSE.
"""

import unittest


class TestMCPServerThreadStop(unittest.TestCase):
    def test_stop_exits_uvicorn_without_attributeerror(self):
        from src.mcp_server import MCPServerThread
        t = MCPServerThread()
        fake_uvicorn = unittest.mock.MagicMock()
        real_server = unittest.mock.MagicMock()  # stands in for FastMCP app
        t._uvicorn_server = fake_uvicorn
        t._server = real_server
        t.stop()
        self.assertTrue(fake_uvicorn.should_exit)
        real_server.shutdown.assert_not_called()
        self.assertTrue(t._stop_event)
        self.assertIsNone(t._server)
