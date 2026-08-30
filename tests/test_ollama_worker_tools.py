"""Tests for OllamaWorker's MCP-driven tooling.

Covers the regression that the change_visual_state enum was missing valid
actions (e.g. "jump") and included invalid ones (e.g. "perimeter").
"""
from unittest.mock import MagicMock

from src.llm.ollama_worker import OllamaWorker
from src.llm.mcp_client import MCPExecutionBudget, MCPExecutionBudgetError


def test_fallback_tools_include_jump_and_only_valid_actions():
    worker = OllamaWorker(prompt="x", pet_id="kenny")
    tools = worker._fallback_tools()
    cvs = next(t for t in tools if t["function"]["name"] == "change_visual_state")
    enum = cvs["function"]["parameters"]["properties"]["action"]["enum"]
    assert "jump" in enum, "jump must be a selectable action"
    # Previously-leaked invalid actions must be gone.
    assert "perimeter" not in enum
    assert "thinking" not in enum
    assert "sleep" not in enum
    from src.mcp_server import VALID_ACTIONS
    assert set(enum) == set(VALID_ACTIONS)


def test_execute_tool_fallback_emits_signal():
    worker = OllamaWorker(prompt="x", pet_id="kenny")
    worker._mcp = None  # force legacy fallback path
    signals = []
    worker.tool_call_requested.connect(lambda n, a: signals.append((n, a)))
    out = worker._execute_tool("change_visual_state", {"action": "jump"})
    assert signals and signals[0][0] == "change_visual_state"
    assert "jump" in out


def test_execute_tool_uses_mcp_client_when_available():
    worker = OllamaWorker(prompt="x", pet_id="kenny")
    fake = MagicMock()
    fake.call_tool.return_value = '{"status":"ok"}'
    worker._mcp = fake
    out = worker._execute_tool("change_visual_state", {"action": "jump"})
    fake.call_tool.assert_called_once_with("change_visual_state", {"action": "jump"})
    assert "ok" in out


def test_execute_tool_enforces_request_budget():
    worker = OllamaWorker(prompt="x", pet_id="kenny")
    worker._mcp = MagicMock()
    budget = MCPExecutionBudget(max_tool_calls=0)
    try:
        worker._execute_tool("change_visual_state", {"action": "jump"}, budget=budget)
    except MCPExecutionBudgetError as exc:
        assert "tool-call budget" in str(exc)
    else:
        raise AssertionError("over-budget MCP call must fail explicitly")
