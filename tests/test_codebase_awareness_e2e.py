"""End-to-end tests for codebase awareness pipeline."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from utils.security import is_safe_write_path, DATA_DIR, PROJECT_ROOT
from scripts.generate_ast_map import generate_codebase_map


def test_write_sandbox_enforced():
    assert is_safe_write_path(os.path.join(PROJECT_ROOT, "src", "pet_window.py")) is False
    assert is_safe_write_path(os.path.join(PROJECT_ROOT, "tests", "test_fsm.py")) is False
    assert is_safe_write_path(os.path.join(PROJECT_ROOT, "daemon.py")) is False
    assert is_safe_write_path(os.path.join(DATA_DIR, "..", "src", "evil.py")) is False
    assert is_safe_write_path("C:/Windows/System32/evil.exe") is False

    assert is_safe_write_path(os.path.join(DATA_DIR, "test.json")) is True
    assert is_safe_write_path(os.path.join(DATA_DIR, "blackmail", "evidence.png")) is True


def test_ast_map_exists_and_valid(tmp_path):
    map_path = tmp_path / "codebase_map.json"
    generate_codebase_map(os.path.join(PROJECT_ROOT, "src"), str(map_path))

    with open(map_path, encoding="utf-8") as f:
        map_data = json.load(f)

    assert "classes" in map_data
    assert "functions" in map_data
    assert "modules" in map_data
    assert "PetWindow" in map_data["classes"]
    assert "PetFSM" in map_data["classes"]
    assert "OpencodeWorker" in map_data["classes"]
    assert len(map_data["classes"]) > 20
