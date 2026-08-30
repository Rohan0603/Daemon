"""Tests for OpencodeWorker's MCP tool-call forwarding.

The opencode engine previously had no tool wiring at all. These tests verify
the response parsing that extracts tool calls and the forwarding that executes
them against the Daemon MCP server.
"""
from unittest.mock import MagicMock

from src.llm.opencode_worker import OpencodeWorker
from src.llm.mcp_client import MCPExecutionBudget


def test_extract_tool_calls_top_level():
    data = {"tool_calls": [{"function": {"name": "change_visual_state",
                                         "arguments": {"action": "jump"}}}]}
    calls = OpencodeWorker._extract_tool_calls(data)
    assert calls[0]["name"] == "change_visual_state"
    assert calls[0]["arguments"] == {"action": "jump"}


def test_extract_tool_calls_string_args_parsed():
    data = {"tool_calls": [{"function": {"name": "x", "arguments": '{"a": 1}'}}]}
    calls = OpencodeWorker._extract_tool_calls(data)
    assert calls[0]["arguments"] == {"a": 1}


def test_extract_tool_calls_message_shape():
    data = {"message": {"tool_calls": [{"function": {"name": "y", "arguments": {}}}]}}
    calls = OpencodeWorker._extract_tool_calls(data)
    assert calls[0]["name"] == "y"


def test_extract_tool_calls_part_shape():
    data = {"parts": [{"type": "tool_call", "name": "z", "arguments": {"b": 2}}]}
    calls = OpencodeWorker._extract_tool_calls(data)
    assert calls[0]["name"] == "z"
    assert calls[0]["arguments"] == {"b": 2}


def test_extract_tool_calls_none_when_absent():
    assert OpencodeWorker._extract_tool_calls({"parts": [{"type": "text", "text": "hi"}]}) == []


def test_forward_tool_calls_invokes_mcp_client():
    worker = OpencodeWorker(prompt="x")
    worker._mcp = MagicMock()
    worker._mcp.call_tool.return_value = "ok"
    data = {"tool_calls": [{"function": {"name": "change_visual_state",
                                        "arguments": {"action": "jump"}}}]}
    worker._forward_tool_calls(data)
    worker._mcp.call_tool.assert_called_once_with("change_visual_state", {"action": "jump"})


def test_forward_tool_calls_stops_at_budget():
    worker = OpencodeWorker(prompt="x")
    worker._mcp = MagicMock()
    worker._tool_budget = MCPExecutionBudget(max_tool_calls=0)
    data = {"tool_calls": [{"function": {"name": "change_visual_state",
                                         "arguments": {"action": "jump"}}}]}
    worker._forward_tool_calls(data)
    worker._mcp.call_tool.assert_not_called()
