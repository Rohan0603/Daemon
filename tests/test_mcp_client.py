"""Tests for src.llm.mcp_client (DaemonMCPClient).

These exercise the async → sync wrappers and the schema/text conversion using
a faked MCP SSE session, so no live MCP server is required.
"""
import json
from contextlib import asynccontextmanager
from unittest.mock import MagicMock, patch

from src.llm.mcp_client import DaemonMCPClient, _extract_text, _tool_to_llm_schema


class _FakeTool:
    name = "change_visual_state"
    description = "Change the pet's visual state."
    inputSchema = {"type": "object", "properties": {"action": {"type": "string"}}}


class _FakeCallResult:
    isError = False

    def __init__(self, payload):
        self.content = [MagicMock(text=json.dumps(payload))]


class FakeSession:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def initialize(self):
        return None

    async def list_tools(self):
        res = MagicMock()
        res.tools = [_FakeTool()]
        return res

    async def call_tool(self, name, args):
        return _FakeCallResult({"status": "ok", "action": args.get("action")})


@asynccontextmanager
async def _fake_sse(url):
    yield (MagicMock(), MagicMock())


def test_tool_to_llm_schema():
    schema = _tool_to_llm_schema(_FakeTool())
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "change_visual_state"
    assert "action" in schema["function"]["parameters"]["properties"]


def test_extract_text_flattens_content():
    class P:
        text = "hello"

    res = MagicMock()
    res.content = [P(), P()]
    assert _extract_text(res) == "hello\nhello"


@patch("src.llm.mcp_client.ClientSession", FakeSession)
@patch("src.llm.mcp_client.sse_client", _fake_sse)
def test_list_and_call_tools_via_fake_session():
    client = DaemonMCPClient("http://127.0.0.1:4097/sse")
    schema = client.list_tools()
    assert schema[0]["function"]["name"] == "change_visual_state"
    out = client.call_tool("change_visual_state", {"action": "jump"})
    assert "jump" in out


@patch("src.llm.mcp_client.ClientSession", FakeSession)
@patch("src.llm.mcp_client.sse_client", _fake_sse)
def test_get_tool_schema_is_cached():
    client = DaemonMCPClient("http://127.0.0.1:4097/sse")
    assert client.get_tool_schema() is client.get_tool_schema()


def test_get_tool_schema_returns_empty_on_failure_no_hang():
    """A broken/slow MCP server (e.g. a zombie holding port 4097) must not
    hang the worker thread forever — the call is bounded by a timeout and the
    schema falls back to [] so the LLM request still proceeds."""
    import asyncio

    client = DaemonMCPClient("http://127.0.0.1:4097/sse")

    def _boom(*a, **k):
        raise asyncio.TimeoutError("simulated dead server")

    client.list_tools = _boom
    schema = client.get_tool_schema()
    assert schema == [], "dead MCP server must fall back to empty schema"
    # Second call must not retry the failing fetch (cached empty result).
    assert client.get_tool_schema() == []
