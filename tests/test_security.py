import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from utils.security import is_safe_write_path, get_safe_data_path, PROJECT_ROOT, DATA_DIR


def test_is_safe_write_path_allows_data_dir():
    assert is_safe_write_path(os.path.join(DATA_DIR, "test.json")) is True
    assert is_safe_write_path(os.path.join(DATA_DIR, "subdir", "test.txt")) is True


def test_is_safe_write_path_blocks_src():
    assert is_safe_write_path(os.path.join(PROJECT_ROOT, "src", "pet_window.py")) is False
    assert is_safe_write_path(os.path.join(PROJECT_ROOT, "src", "mcp_server.py")) is False


def test_is_safe_write_path_blocks_tests():
    assert is_safe_write_path(os.path.join(PROJECT_ROOT, "tests", "test_fsm.py")) is False


def test_is_safe_write_path_blocks_root_files():
    assert is_safe_write_path(os.path.join(PROJECT_ROOT, "daemon.py")) is False
    assert is_safe_write_path(os.path.join(PROJECT_ROOT, "README.md")) is False


def test_is_safe_write_path_blocks_traversal():
    assert is_safe_write_path(os.path.join(DATA_DIR, "..", "src", "evil.py")) is False
    assert is_safe_write_path(os.path.join(DATA_DIR, "subdir", "..", "..", "src", "evil.py")) is False


def test_is_safe_write_path_blocks_absolute_outside():
    assert is_safe_write_path("C:/Windows/System32/evil.exe") is False
    assert is_safe_write_path("/etc/passwd") is False


def test_is_safe_write_path_blocks_relative_traversal():
    assert is_safe_write_path("../../etc/passwd") is False
    assert is_safe_write_path("..\\..\\windows\\system32") is False


def test_get_safe_data_path_success():
    result = get_safe_data_path("blackmail/evidence.png")
    expected = os.path.normpath(os.path.join(DATA_DIR, "blackmail/evidence.png"))
    assert result == expected


def test_get_safe_data_path_raises_on_traversal():
    with pytest.raises(ValueError, match="Path escapes data directory"):
        get_safe_data_path("../../src/pet_window.py")


def test_get_safe_data_path_raises_on_absolute():
    with pytest.raises(ValueError, match="Path escapes data directory"):
        get_safe_data_path("C:/Windows/System32")
