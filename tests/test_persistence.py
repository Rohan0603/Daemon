import json
import tempfile
import os
import pytest


def test_save_and_load_roundtrip(tmp_path):
    from src.persistence import save_state, load_state
    path = str(tmp_path / "state.json")
    save_state({"mood": 5, "interactions": 42, "runtime_seconds": 3600, "skill_greeted": True}, path)
    result = load_state(path)
    assert result["mood"] == 5
    assert result["interactions"] == 42
    assert result["runtime_seconds"] == 3600
    assert result["skill_greeted"] is True


def test_load_missing_file_returns_defaults(tmp_path):
    from src.persistence import load_state
    path = str(tmp_path / "nonexistent.json")
    result = load_state(path)
    assert result == {"mood": 0, "interactions": 0, "runtime_seconds": 0, "skill_greeted": False, "first_run_done": False}


def test_load_corrupt_file_returns_defaults(tmp_path):
    from src.persistence import load_state
    path = str(tmp_path / "corrupt.json")
    with open(path, "w") as f:
        f.write("{{{{ not valid json")
    result = load_state(path)
    assert result == {"mood": 0, "interactions": 0, "runtime_seconds": 0, "skill_greeted": False, "first_run_done": False}


def test_load_partial_file_fills_defaults(tmp_path):
    from src.persistence import load_state
    path = str(tmp_path / "partial.json")
    with open(path, "w") as f:
        json.dump({"mood": 3}, f)
    result = load_state(path)
    assert result["mood"] == 3
    assert result["interactions"] == 0
    assert result["runtime_seconds"] == 0
    assert result["skill_greeted"] is False
    assert result["first_run_done"] is False


def test_save_state_is_atomic():
    import os
    from src.persistence import save_state, _DEFAULT_PATH
    path = _DEFAULT_PATH
    tmp_path = path + ".tmp"
    for p in [path, tmp_path]:
        if os.path.exists(p):
            os.unlink(p)
    try:
        save_state({"mood": 5, "interactions": 10, "runtime_seconds": 60,
                     "skill_greeted": True, "first_run_done": True})
        assert not os.path.exists(tmp_path)
        assert os.path.exists(path)
    finally:
        for p in [path, tmp_path]:
            if os.path.exists(p):
                os.unlink(p)


class TestPersistenceEdgeCases:
    def test_save_with_empty_dict(self, tmp_path):
        from src.persistence import save_state, load_state
        path = str(tmp_path / "state.json")
        save_state({}, path)
        result = load_state(path)
        assert result == {"mood": 0, "interactions": 0, "runtime_seconds": 0, "skill_greeted": False, "first_run_done": False}

    def test_save_with_nested_data(self, tmp_path):
        from src.persistence import save_state, load_state
        path = str(tmp_path / "state.json")
        data = {"mood": 5, "interactions": 10, "runtime_seconds": 3600, "skill_greeted": True, "first_run_done": False}
        save_state(data, path)
        result = load_state(path)
        assert result["mood"] == 5
        assert result["interactions"] == 10
        assert result["runtime_seconds"] == 3600
        assert result["skill_greeted"] is True

    def test_partial_file_has_all_defaults(self, tmp_path):
        from src.persistence import save_state, load_state
        path = str(tmp_path / "state.json")
        save_state({"mood": 3}, path)
        result = load_state(path)
        assert result["mood"] == 3
        assert result["interactions"] == 0
        assert result["runtime_seconds"] == 0
        assert result["skill_greeted"] is False
        assert result["first_run_done"] is False

    def test_load_on_both_main_and_bak_corrupt(self, tmp_path):
        from src.persistence import load_state
        path = str(tmp_path / "state.json")
        with open(path, "w") as f:
            f.write("corrupt")
        bak_path = path + ".bak"
        with open(bak_path, "w") as f:
            f.write("also corrupt")
        result = load_state(path)
        assert result == {"mood": 0, "interactions": 0, "runtime_seconds": 0, "skill_greeted": False, "first_run_done": False}

    def test_bak_created_on_save(self, tmp_path):
        from src.persistence import save_state
        from pathlib import Path
        path = str(tmp_path / "state.json")
        save_state({"mood": 1}, path)
        assert not Path(path + ".bak").exists()
        save_state({"mood": 2}, path)
        assert Path(path + ".bak").exists()

    def test_save_and_load_special_types(self, tmp_path):
        from src.persistence import save_state, load_state
        path = str(tmp_path / "state.json")
        data = {"mood": 0, "interactions": 5, "runtime_seconds": 0, "skill_greeted": None, "first_run_done": True}
        save_state(data, path)
        result = load_state(path)
        assert result["skill_greeted"] is None
        assert result["first_run_done"] is True

