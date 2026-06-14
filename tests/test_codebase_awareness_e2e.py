"""End-to-end tests for codebase awareness pipeline."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mcp_server import MCPHandler
from utils.security import is_safe_write_path, DATA_DIR, PROJECT_ROOT
from unittest.mock import MagicMock


def _handler():
    handler = object.__new__(MCPHandler)
    handler.server = MagicMock()
    handler.server.fsm_bridge = MagicMock()
    return handler


def test_full_read_pipeline():
    handler = _handler()

    # 1. List src directory
    resp = handler._handle_tools_call({
        "name": "list_directory",
        "arguments": {"relative_path": "src"}
    })
    assert "result" in resp
    content = json.loads(resp["result"]["content"][0]["text"])
    names = [c["name"] for c in content]
    assert "pet_window.py" in names
    assert "mcp_server.py" in names
    assert "constants.py" in names

    # 2. Read a specific file
    resp = handler._handle_tools_call({
        "name": "read_file",
        "arguments": {"file_path": "src/constants.py", "start_line": 1, "end_line": 30}
    })
    assert "result" in resp
    text = resp["result"]["content"][0]["text"]
    assert "BOREDOM_TIMEOUT_SEC" in text or "MAX_IDLE_BACKOFF_SEC" in text

    # 3. Search for a class
    resp = handler._handle_tools_call({
        "name": "search_codebase",
        "arguments": {"search_term": "class PetWindow"}
    })
    assert "result" in resp
    results = json.loads(resp["result"]["content"][0]["text"])
    assert len(results) >= 1
    assert any("pet_window.py" in r["file"] for r in results)


def test_write_sandbox_enforced():
    assert is_safe_write_path(os.path.join(PROJECT_ROOT, "src", "pet_window.py")) is False
    assert is_safe_write_path(os.path.join(PROJECT_ROOT, "tests", "test_fsm.py")) is False
    assert is_safe_write_path(os.path.join(PROJECT_ROOT, "daemon.py")) is False
    assert is_safe_write_path(os.path.join(DATA_DIR, "..", "src", "evil.py")) is False
    assert is_safe_write_path("C:/Windows/System32/evil.exe") is False

    assert is_safe_write_path(os.path.join(DATA_DIR, "test.json")) is True
    assert is_safe_write_path(os.path.join(DATA_DIR, "blackmail", "evidence.png")) is True


def test_ast_map_exists_and_valid():
    map_path = os.path.join(os.path.dirname(__file__), "..", "data", "codebase_map.json")
    assert os.path.exists(map_path), "codebase_map.json not found - run daemon.py first"

    with open(map_path) as f:
        map_data = json.load(f)

    assert "classes" in map_data
    assert "functions" in map_data
    assert "modules" in map_data
    assert "PetWindow" in map_data["classes"]
    assert "PetFSM" in map_data["classes"]
    assert "OpencodeWorker" in map_data["classes"]
    assert "MCPHandler" in map_data["classes"]
    assert "MCPServer" in map_data["classes"]
    assert len(map_data["classes"]) > 20


def test_read_write_link():
    handler = _handler()

    # Verify read tools expose what the write sandbox protects
    resp = handler._handle_tools_call({
        "name": "read_file",
        "arguments": {"file_path": "src/utils/security.py"}
    })
    assert "result" in resp
    text = resp["result"]["content"][0]["text"]
    assert "is_safe_write_path" in text
