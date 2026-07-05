"""End-to-end tests for codebase awareness pipeline."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from utils.security import is_safe_write_path, DATA_DIR, PROJECT_ROOT


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
    assert "MCPServer" in map_data["classes"]
    assert len(map_data["classes"]) > 20
